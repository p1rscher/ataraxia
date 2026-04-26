import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands

from core import database_pg as db

logger = logging.getLogger(__name__)

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_SUITS = ["♠", "♥", "♦", "♣"]

WORK_FLAVORS = [
    ("baker", "You baked fresh bread for the whole neighborhood."),
    ("developer", "You squashed a nasty production bug."),
    ("gardener", "You restored a beautiful garden."),
    ("chef", "You served a five-star dinner service."),
    ("taxi driver", "You drove passengers across the city."),
    ("mechanic", "You repaired a broken engine."),
    ("DJ", "You played a packed club set."),
    ("fisher", "You came back with a huge catch."),
    ("photographer", "You shot a full wedding event."),
    ("teacher", "You tutored a student through finals."),
]

CRIME_FLAVORS = [
    ("robbed a bank", "The vault was wide open."),
    ("hacked a crypto wallet", "The exploit worked perfectly."),
    ("rigged a casino table", "The house never saw it coming."),
    ("stole a diamond", "It shines almost too brightly."),
    ("printed counterfeit cash", "It passed the first inspection."),
]

CRIME_FAIL_FLAVORS = [
    "The police caught you immediately.",
    "A security camera recorded everything.",
    "You tripped while trying to escape.",
    "Your partner sold you out.",
    "A guard dog ruined the whole plan.",
]

BEG_SUCCESS = [
    "A kind stranger handed you some coins.",
    "Someone felt sorry for you.",
    "A wealthy passerby dropped you a tip.",
    "An old traveler shared part of their savings.",
    "A child gave you their spare pocket money.",
]

BEG_FAIL = [
    "Nobody wanted to help today.",
    "People just walked by without stopping.",
    "Someone gave you advice instead of money.",
    "A dog barked at you and everyone left.",
    "You lost your nerve before asking.",
]

BUILTIN_SHOP_ITEMS = {
    "shield": {
        "item_key": "shield",
        "name": "Shield",
        "description": "Blocks one /rob attempt automatically.",
        "price": 1500,
        "item_type": "shield",
    },
    "xpboost": {
        "item_key": "xpboost",
        "name": "XP Booster",
        "description": "Consumable. Use it to activate 2x XP for 2 hours.",
        "price": 2500,
        "item_type": "xp_boost",
        "boost_multiplier": 2.0,
        "boost_hours": 2,
    },
}


def format_cooldown(expires: datetime) -> str:
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return f"<t:{int(expires.timestamp())}:R>"


def get_streak_multiplier(streak: int) -> float:
    if streak <= 1:
        return 1.0
    if streak <= 7:
        return 1.0 + (streak - 1) * (2.0 / 6.0)
    if streak <= 30:
        return 3.0 + (streak - 7) * (7.0 / 23.0)
    return 10.0


def clean_item_key(raw: str) -> str:
    cleaned = []
    for char in raw.lower().strip():
        if char.isalnum() or char in {"_", "-"}:
            cleaned.append(char)
        elif char in {" ", "/"}:
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    while "__" in result:
        result = result.replace("__", "_")
    return result[:32]


def hand_value(hand: list[str]) -> int:
    total = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank == "A":
            aces += 1
            total += 11
        elif rank in {"J", "Q", "K"}:
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def is_blackjack(hand: list[str]) -> bool:
    return len(hand) == 2 and hand_value(hand) == 21


def render_hand(hand: list[str], hide_second: bool = False) -> str:
    if hide_second and len(hand) > 1:
        return f"{hand[0]} ??"
    return " ".join(hand)


def generate_crash_point() -> float:
    value = random.random()
    return round(max(1.05, min(15.0, 0.99 / (1 - value))), 2)


class BlackjackView(discord.ui.View):
    def __init__(self, player_id: int, guild_id: int, bet: int, currency_symbol: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.guild_id = guild_id
        self.bet = bet
        self.currency_symbol = currency_symbol
        self.player_hand = [self.draw_card(), self.draw_card()]
        self.dealer_hand = [self.draw_card(), self.draw_card()]
        self.resolved = False
        self.message: Optional[discord.Message] = None

    def draw_card(self) -> str:
        return f"{random.choice(CARD_RANKS)}{random.choice(CARD_SUITS)}"

    def _disable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def build_embed(self, reveal_dealer: bool = False, result_text: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.blurple())
        embed.add_field(
            name="Dealer",
            value=f"{render_hand(self.dealer_hand, hide_second=not reveal_dealer)}\nValue: {'?' if not reveal_dealer else hand_value(self.dealer_hand)}",
            inline=False,
        )
        embed.add_field(
            name="Your Hand",
            value=f"{render_hand(self.player_hand)}\nValue: {hand_value(self.player_hand)}",
            inline=False,
        )
        embed.add_field(name="Bet", value=f"{self.currency_symbol} **{self.bet:,}**", inline=False)
        if result_text:
            embed.description = result_text
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This blackjack game is not yours.", ephemeral=True)
            return False
        return True

    async def settle(self, interaction: Optional[discord.Interaction], reason: Optional[str] = None):
        if self.resolved:
            return
        self.resolved = True
        self._disable_buttons()

        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card())

        player_total = hand_value(self.player_hand)
        dealer_total = hand_value(self.dealer_hand)

        if player_total > 21:
            result_text = reason or "You busted and lost your bet."
        elif dealer_total > 21 or player_total > dealer_total:
            payout = self.bet * 2
            await db.add_coins(self.player_id, self.guild_id, payout, "Blackjack win")
            result_text = reason or f"You win and receive {self.currency_symbol} **{payout:,}**."
        elif player_total < dealer_total:
            result_text = reason or "The dealer wins this round."
        else:
            await db.add_coins(self.player_id, self.guild_id, self.bet, "Blackjack push")
            result_text = reason or f"Push. Your {self.currency_symbol} **{self.bet:,}** bet was returned."

        updated_embed = self.build_embed(reveal_dealer=True, result_text=result_text)

        if interaction:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(embed=updated_embed, view=self)
                else:
                    await interaction.edit_original_response(embed=updated_embed, view=self)
            else:
                await interaction.response.edit_message(embed=updated_embed, view=self)
        elif self.message:
            await self.message.edit(embed=updated_embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.draw_card())
        if hand_value(self.player_hand) > 21:
            await self.settle(interaction, reason="You busted and lost your bet.")
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.settle(interaction)

    async def on_timeout(self):
        if self.resolved:
            return
        await self.settle(None, reason="Time ran out. The dealer played out the hand.")


class CrashView(discord.ui.View):
    def __init__(self, player_id: int, guild_id: int, bet: int, currency_symbol: str):
        super().__init__(timeout=45)
        self.player_id = player_id
        self.guild_id = guild_id
        self.bet = bet
        self.currency_symbol = currency_symbol
        self.current_multiplier = 1.00
        self.crash_point = generate_crash_point()
        self.resolved = False
        self.message: Optional[discord.Message] = None
        self.loop_task: Optional[asyncio.Task] = None

    def build_embed(self, result_text: Optional[str] = None) -> discord.Embed:
        embed = discord.Embed(
            title="📈 Crash",
            color=discord.Color.orange(),
            description=result_text or "Watch the multiplier rise and cash out before it crashes.",
        )
        embed.add_field(name="Bet", value=f"{self.currency_symbol} **{self.bet:,}**", inline=True)
        embed.add_field(name="Multiplier", value=f"**{self.current_multiplier:.2f}x**", inline=True)
        return embed

    def _disable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This crash game is not yours.", ephemeral=True)
            return False
        return True

    async def start(self):
        self.loop_task = asyncio.create_task(self.run_loop())

    async def run_loop(self):
        try:
            while not self.resolved:
                await asyncio.sleep(1.2)
                increment = random.uniform(0.10, 0.45 if self.current_multiplier < 2 else 0.30)
                self.current_multiplier = round(self.current_multiplier + increment, 2)

                if self.current_multiplier >= self.crash_point:
                    self.current_multiplier = self.crash_point
                    await self.finish_crash()
                    return

                if self.message:
                    await self.message.edit(embed=self.build_embed(), view=self)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error(f"Crash game loop failed: {exc}", exc_info=True)

    async def finish_crash(self):
        if self.resolved:
            return
        self.resolved = True
        self._disable_buttons()
        if self.message:
            await self.message.edit(
                embed=self.build_embed(result_text=f"The graph crashed at **{self.crash_point:.2f}x**. You lost your bet."),
                view=self,
            )

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success)
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            await interaction.response.send_message("This crash game is already over.", ephemeral=True)
            return
        self.resolved = True
        self._disable_buttons()
        payout = max(1, int(self.bet * self.current_multiplier))
        await db.add_coins(self.player_id, self.guild_id, payout, "Crash cash out")
        if self.loop_task:
            self.loop_task.cancel()
        await interaction.response.edit_message(
            embed=self.build_embed(result_text=f"You cashed out at **{self.current_multiplier:.2f}x** and received {self.currency_symbol} **{payout:,}**."),
            view=self,
        )

    async def on_timeout(self):
        if self.resolved:
            return
        await self.finish_crash()


class EconomyCog(commands.Cog):
    @commands.hybrid_group(name="shopadmin", description="Manage the economy shop")
    async def shopadmin_group(self, ctx: commands.Context):
        pass

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _parse_amount(self, ctx: commands.Context, amount_text: str, available: int) -> Optional[int]:
        if amount_text.lower() == "all":
            amount = available
        else:
            try:
                amount = int(amount_text)
            except ValueError:
                await ctx.send("Please enter a valid number or `all`.", ephemeral=True)
                return None

        if amount <= 0:
            await ctx.send("The amount must be greater than zero.", ephemeral=True)
            return None
        if amount > available:
            await ctx.send("You do not have enough funds for that.", ephemeral=True)
            return None
        return amount

    async def _take_bet(self, ctx: commands.Context, amount_text: str, reason: str) -> Optional[int]:
        assert ctx.guild.id is not None
        wallet = await db.get_wallet(ctx.author.id, ctx.guild.id)
        amount = await self._parse_amount(ctx, amount_text, wallet['cash'])
        if amount is None:
            return None
        success = await db.remove_coins(ctx.author.id, ctx.guild.id, amount, reason)
        if not success:
            await ctx.send("You do not have enough cash for that bet.", ephemeral=True)
            return None
        return amount

    async def _get_shop_catalog(self, guild_id: int) -> dict[str, dict]:
        catalog = {key: dict(value) for key, value in BUILTIN_SHOP_ITEMS.items()}
        rows = await db.get_shop_items(guild_id)
        for row in rows:
            catalog[row['item_key']] = dict(row)
        return catalog

    def _shop_display_line(self, item: dict, currency_symbol: str) -> str:
        extra = ""
        if item['item_type'] == "role":
            extra = "Role unlock"
        elif item['item_type'] == "shield":
            extra = "Passive item"
        elif item['item_type'] == "xp_boost":
            extra = f"Consumable, {item.get('boost_multiplier', 2.0):.1f}x XP for {item.get('boost_hours', 2)}h"
        return f"`{item['item_key']}` • {currency_symbol} **{item['price']:,}**\n{item['description']}\n*{extra}*"

    @commands.hybrid_command(name="balance", description="View a wallet balance")
    @commands.guild_only()
    async def balance(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        assert ctx.guild.id is not None
        target = user or ctx.author
        wallet = await db.get_wallet(target.id, ctx.guild.id)
        settings = await db.get_economy_settings(ctx.guild.id)
        active_boost = await db.get_active_xp_boost(target.id, ctx.guild.id)
        symbol = settings['currency_symbol']

        embed = discord.Embed(title=f"{target.display_name}'s Balance", color=discord.Color.gold())
        embed.add_field(name="Cash", value=f"{symbol} **{wallet['cash']:,}**", inline=True)
        embed.add_field(name="Bank", value=f"{symbol} **{wallet['bank']:,}**", inline=True)
        embed.add_field(name="Net Worth", value=f"{symbol} **{wallet['cash'] + wallet['bank']:,}**", inline=True)
        embed.add_field(name="Daily Bank Interest", value=f"**{settings['bank_interest_rate'] * 100:.2f}%**", inline=False)
        if active_boost:
            embed.add_field(
                name="Active XP Boost",
                value=f"**{active_boost['multiplier']:.2f}x** until {format_cooldown(active_boost['expires_at'])}",
                inline=False,
            )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deposit", description="Deposit coins into your bank")
    @commands.guild_only()
    @app_commands.describe(amount="Amount to deposit or 'all'")
    async def deposit(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        wallet = await db.get_wallet(ctx.author.id, ctx.guild.id)
        amount_int = await self._parse_amount(ctx, amount, wallet['cash'])
        if amount_int is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        if await db.deposit_coins(ctx.author.id, ctx.guild.id, amount_int):
            await ctx.send(f"🏦 Deposited {settings['currency_symbol']} **{amount_int:,}** into your bank.")
        else:
            await ctx.send("The deposit failed because you do not have enough cash or the bank limit was reached.", ephemeral=True)

    @commands.hybrid_command(name="withdraw", description="Withdraw coins from your bank")
    @commands.guild_only()
    @app_commands.describe(amount="Amount to withdraw or 'all'")
    async def withdraw(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        wallet = await db.get_wallet(ctx.author.id, ctx.guild.id)
        amount_int = await self._parse_amount(ctx, amount, wallet['bank'])
        if amount_int is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        if await db.withdraw_coins(ctx.author.id, ctx.guild.id, amount_int):
            await ctx.send(f"🏦 Withdrew {settings['currency_symbol']} **{amount_int:,}** from your bank.")
        else:
            await ctx.send("You do not have enough coins in the bank.", ephemeral=True)

    @commands.hybrid_command(name="daily", description="Claim your daily reward")
    @commands.guild_only()
    async def daily(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        streak_data = await db.get_streak(ctx.author.id, ctx.guild.id)
        last_daily = streak_data['last_daily']
        now = datetime.now(timezone.utc)

        if last_daily:
            if last_daily.tzinfo is None:
                last_daily = last_daily.replace(tzinfo=timezone.utc)
            hours_since = (now - last_daily).total_seconds() / 3600
            if hours_since < 24:
                await ctx.send(
                    f"You already claimed your daily reward. Come back {format_cooldown(last_daily + timedelta(hours=24))}.",
                    ephemeral=True,
                )
                return
            new_streak = 1 if hours_since > 48 else streak_data['daily_streak'] + 1
        else:
            new_streak = 1

        multiplier = get_streak_multiplier(new_streak)
        amount = int(settings['daily_base'] * multiplier)
        await db.add_coins(ctx.author.id, ctx.guild.id, amount, f"Daily streak {new_streak}")
        await db.update_daily_streak(ctx.author.id, ctx.guild.id, new_streak)

        embed = discord.Embed(title="📅 Daily Reward", color=discord.Color.green())
        embed.add_field(name="Reward", value=f"{settings['currency_symbol']} **{amount:,}**", inline=True)
        embed.add_field(name="Streak", value=f"🔥 **{new_streak} days**", inline=True)
        embed.add_field(name="Multiplier", value=f"**{multiplier:.1f}x**", inline=True)
        if new_streak < 30:
            embed.set_footer(text=f"Tomorrow: {get_streak_multiplier(new_streak + 1):.1f}x reward multiplier")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="weekly", description="Claim your weekly reward")
    @commands.guild_only()
    async def weekly(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        streak_data = await db.get_streak(ctx.author.id, ctx.guild.id)
        last_weekly = streak_data['last_weekly']
        now = datetime.now(timezone.utc)

        if last_weekly:
            if last_weekly.tzinfo is None:
                last_weekly = last_weekly.replace(tzinfo=timezone.utc)
            if (now - last_weekly).total_seconds() < 168 * 3600:
                await ctx.send(
                    f"You already claimed your weekly reward. Come back {format_cooldown(last_weekly + timedelta(days=7))}.",
                    ephemeral=True,
                )
                return

        amount = settings['weekly_base']
        await db.add_coins(ctx.author.id, ctx.guild.id, amount, "Weekly reward")
        await db.update_weekly_timestamp(ctx.author.id, ctx.guild.id)
        await ctx.send(f"📆 You claimed {settings['currency_symbol']} **{amount:,}** from your weekly reward.")

    @commands.hybrid_command(name="work", description="Work a job for coins")
    @commands.guild_only()
    async def work(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        cooldown = await db.get_economy_cooldown(ctx.author.id, ctx.guild.id, "work")
        if cooldown:
            await ctx.send(f"You are still on shift. Try again {format_cooldown(cooldown)}.", ephemeral=True)
            return

        job, flavor = random.choice(WORK_FLAVORS)
        amount = random.randint(settings['work_min'], settings['work_max'])
        await db.add_coins(ctx.author.id, ctx.guild.id, amount, f"Work: {job}")
        await db.set_economy_cooldown(ctx.author.id, ctx.guild.id, "work", settings['work_cooldown'])
        await ctx.send(
            embed=discord.Embed(
                title="🔨 Work Complete",
                description=f"{flavor}\nYou worked as a **{job}** and earned {settings['currency_symbol']} **{amount:,}**.",
                color=discord.Color.blue(),
            )
        )

    @commands.hybrid_command(name="crime", description="Commit a crime for a risky reward")
    @commands.guild_only()
    async def crime(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        cooldown = await db.get_economy_cooldown(ctx.author.id, ctx.guild.id, "crime")
        if cooldown:
            await ctx.send(f"You need to lay low. Try again {format_cooldown(cooldown)}.", ephemeral=True)
            return

        await db.set_economy_cooldown(ctx.author.id, ctx.guild.id, "crime", settings['crime_cooldown'])
        success = random.randint(1, 100) <= settings['crime_success_rate']

        if success:
            amount = random.randint(settings['crime_min'], settings['crime_max'])
            action, flavor = random.choice(CRIME_FLAVORS)
            await db.add_coins(ctx.author.id, ctx.guild.id, amount, f"Crime: {action}")
            embed = discord.Embed(
                title="🦹 Crime Successful",
                description=f"You {action}. {flavor}\nYou earned {settings['currency_symbol']} **{amount:,}**.",
                color=discord.Color.dark_green(),
            )
        else:
            fine = random.randint(settings['crime_fine_min'], settings['crime_fine_max'])
            wallet = await db.get_wallet(ctx.author.id, ctx.guild.id)
            actual_fine = min(fine, wallet['cash'])
            if actual_fine > 0:
                await db.remove_coins(ctx.author.id, ctx.guild.id, actual_fine, "Crime fine")
            embed = discord.Embed(
                title="🚔 Crime Failed",
                description=f"{random.choice(CRIME_FAIL_FLAVORS)}\nYou paid {settings['currency_symbol']} **{actual_fine:,}** in fines.",
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="beg", description="Beg for a small amount of coins")
    @commands.guild_only()
    async def beg(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        cooldown = await db.get_economy_cooldown(ctx.author.id, ctx.guild.id, "beg")
        if cooldown:
            await ctx.send(f"You begged recently already. Try again {format_cooldown(cooldown)}.", ephemeral=True)
            return

        await db.set_economy_cooldown(ctx.author.id, ctx.guild.id, "beg", settings['beg_cooldown'])
        if random.randint(1, 100) <= settings['beg_nothing_rate']:
            await ctx.send(
                embed=discord.Embed(title="🙏 Begging", description=random.choice(BEG_FAIL), color=discord.Color.dark_grey())
            )
            return

        amount = random.randint(settings['beg_min'], settings['beg_max'])
        await db.add_coins(ctx.author.id, ctx.guild.id, amount, "Begging")
        await ctx.send(
            embed=discord.Embed(
                title="🙏 Begging",
                description=f"{random.choice(BEG_SUCCESS)}\nYou received {settings['currency_symbol']} **{amount:,}**.",
                color=discord.Color.green(),
            )
        )

    @commands.hybrid_command(name="gift", description="Gift coins to another member")
    @commands.guild_only()
    @app_commands.describe(user="Member to receive the gift", amount="Amount of coins to send")
    async def gift(self, ctx: commands.Context, user: discord.Member, amount: int):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        if user.id == ctx.author.id:
            await ctx.send("You cannot gift coins to yourself.", ephemeral=True)
            return
        if user.bot:
            await ctx.send("You cannot gift coins to bots.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.send("The gift amount must be greater than zero.", ephemeral=True)
            return

        success = await db.transfer_coins(ctx.author.id, user.id, ctx.guild.id, amount, settings['gift_tax_percent'])
        if not success:
            await ctx.send("You do not have enough cash for that gift.", ephemeral=True)
            return

        tax = int(amount * settings['gift_tax_percent'] / 100)
        received = amount - tax
        description = f"You sent {user.mention} {settings['currency_symbol']} **{received:,}**."
        if tax > 0:
            description += f"\nTax paid: {settings['currency_symbol']} **{tax:,}**"
        await ctx.send(embed=discord.Embed(title="🎁 Gift Sent", description=description, color=discord.Color.green()))

    @commands.hybrid_command(name="rob", description="Try to rob another member")
    @commands.guild_only()
    @app_commands.describe(user="Target to rob")
    async def rob(self, ctx: commands.Context, user: discord.Member):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        if user.id == ctx.author.id:
            await ctx.send("You cannot rob yourself.", ephemeral=True)
            return
        if user.bot:
            await ctx.send("Bots do not carry cash.", ephemeral=True)
            return

        cooldown = await db.get_economy_cooldown(ctx.author.id, ctx.guild.id, "rob")
        if cooldown:
            await ctx.send(f"You need to cool down before robbing again. Try again {format_cooldown(cooldown)}.", ephemeral=True)
            return

        victim_wallet = await db.get_wallet(user.id, ctx.guild.id)
        if victim_wallet['cash'] <= 0:
            await ctx.send(f"{user.display_name} does not have any cash to steal.", ephemeral=True)
            return

        await db.set_economy_cooldown(ctx.author.id, ctx.guild.id, "rob", settings['rob_cooldown'])
        shield_count = await db.get_inventory_quantity(user.id, ctx.guild.id, "shield")
        if shield_count > 0:
            await db.remove_inventory_item(user.id, ctx.guild.id, "shield", 1)
            await ctx.send(
                embed=discord.Embed(
                    title="🛡️ Robbery Blocked",
                    description=f"{user.mention}'s shield blocked your robbery attempt. One shield was consumed.",
                    color=discord.Color.orange(),
                )
            )
            return

        success = random.randint(1, 100) <= settings['rob_success_rate']
        if success:
            stolen = max(1, int(victim_wallet['cash'] * random.randint(10, 50) / 100))
            await db.remove_coins(user.id, ctx.guild.id, stolen, f"Robbed by {ctx.author.id}")
            await db.add_coins(ctx.author.id, ctx.guild.id, stolen, f"Robbed {user.id}")
            embed = discord.Embed(
                title="💰 Robbery Successful",
                description=f"You stole {settings['currency_symbol']} **{stolen:,}** from {user.mention}.",
                color=discord.Color.dark_green(),
            )
        else:
            robber_wallet = await db.get_wallet(ctx.author.id, ctx.guild.id)
            fine = max(1, int(robber_wallet['cash'] * settings['rob_fine_percent'] / 100))
            actual_fine = min(fine, robber_wallet['cash'])
            if actual_fine > 0:
                await db.remove_coins(ctx.author.id, ctx.guild.id, actual_fine, "Failed robbery fine")
            embed = discord.Embed(
                title="🚔 Robbery Failed",
                description=f"{user.display_name} caught you. You paid {settings['currency_symbol']} **{actual_fine:,}** in fines.",
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="coinflip", description="Bet on heads or tails")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'", side="Choose heads or tails")
    @app_commands.choices(side=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    async def coinflip(self, ctx: commands.Context, amount: str, side: str):
        assert ctx.guild.id is not None
        bet = await self._take_bet(ctx, amount, "Coinflip bet")
        if bet is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        result = random.choice(["heads", "tails"])
        if result == side:
            payout = bet * 2
            await db.add_coins(ctx.author.id, ctx.guild.id, payout, "Coinflip win")
            description = f"The coin landed on **{result.title()}**. You won {settings['currency_symbol']} **{payout:,}**."
            color = discord.Color.green()
        else:
            description = f"The coin landed on **{result.title()}**. You lost {settings['currency_symbol']} **{bet:,}**."
            color = discord.Color.red()
        await ctx.send(embed=discord.Embed(title="🪙 Coinflip", description=description, color=color))

    @commands.hybrid_command(name="dice", description="Roll against the bot")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'")
    async def dice(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        bet = await self._take_bet(ctx, amount, "Dice bet")
        if bet is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        player_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        if player_roll > bot_roll:
            payout = bet * 2
            await db.add_coins(ctx.author.id, ctx.guild.id, payout, "Dice win")
            description = f"You rolled **{player_roll}**. The bot rolled **{bot_roll}**.\nYou won {settings['currency_symbol']} **{payout:,}**."
            color = discord.Color.green()
        elif player_roll == bot_roll:
            await db.add_coins(ctx.author.id, ctx.guild.id, bet, "Dice push")
            description = f"You both rolled **{player_roll}**. Your bet was returned."
            color = discord.Color.gold()
        else:
            description = f"You rolled **{player_roll}**. The bot rolled **{bot_roll}**.\nYou lost {settings['currency_symbol']} **{bet:,}**."
            color = discord.Color.red()
        await ctx.send(embed=discord.Embed(title="🎲 Dice", description=description, color=color))

    @commands.hybrid_command(name="slots", description="Spin a slot machine")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'")
    async def slots(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        bet = await self._take_bet(ctx, amount, "Slots bet")
        if bet is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        reel = random.choices(["🍒", "🍋", "🍀", "💎", "7️⃣"], weights=[30, 28, 18, 14, 10], k=3)
        multiplier = 0.0
        if reel == ["7️⃣", "7️⃣", "7️⃣"]:
            multiplier = 10.0
        elif reel == ["💎", "💎", "💎"]:
            multiplier = 6.0
        elif len(set(reel)) == 1:
            multiplier = 4.0
        elif reel.count("🍒") >= 2:
            multiplier = 1.5

        if multiplier > 0:
            payout = max(1, int(bet * multiplier))
            await db.add_coins(ctx.author.id, ctx.guild.id, payout, "Slots win")
            description = f"{' '.join(reel)}\nYou won {settings['currency_symbol']} **{payout:,}** at **{multiplier:.1f}x**."
            color = discord.Color.green()
        else:
            description = f"{' '.join(reel)}\nNo payout this time. You lost {settings['currency_symbol']} **{bet:,}**."
            color = discord.Color.red()
        await ctx.send(embed=discord.Embed(title="🎰 Slots", description=description, color=color))

    @commands.hybrid_command(name="roulette", description="Bet on red, black, green, or an exact number")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'", bet="red, black, green, or a number from 0 to 36")
    async def roulette(self, ctx: commands.Context, amount: str, bet: str):
        assert ctx.guild.id is not None
        wager = await self._take_bet(ctx, amount, "Roulette bet")
        if wager is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        bet_clean = bet.strip().lower()
        rolled_number = random.randint(0, 36)
        rolled_color = "green" if rolled_number == 0 else ("red" if rolled_number in RED_NUMBERS else "black")
        multiplier = 0

        if bet_clean in {"red", "black"} and bet_clean == rolled_color:
            multiplier = 2
        elif bet_clean == "green" and rolled_color == "green":
            multiplier = 14
        else:
            try:
                number_bet = int(bet_clean)
            except ValueError:
                await db.add_coins(ctx.author.id, ctx.guild.id, wager, "Roulette refund")
                await ctx.send("Invalid roulette bet. Use red, black, green, or a number from 0 to 36.", ephemeral=True)
                return
            if not 0 <= number_bet <= 36:
                await db.add_coins(ctx.author.id, ctx.guild.id, wager, "Roulette refund")
                await ctx.send("Roulette number bets must be between 0 and 36.", ephemeral=True)
                return
            if number_bet == rolled_number:
                multiplier = 36

        if multiplier > 0:
            payout = wager * multiplier
            await db.add_coins(ctx.author.id, ctx.guild.id, payout, "Roulette win")
            description = f"The wheel landed on **{rolled_number} {rolled_color}**.\nYou won {settings['currency_symbol']} **{payout:,}**."
            color = discord.Color.green()
        else:
            description = f"The wheel landed on **{rolled_number} {rolled_color}**.\nYou lost {settings['currency_symbol']} **{wager:,}**."
            color = discord.Color.red()
        await ctx.send(embed=discord.Embed(title="🎡 Roulette", description=description, color=color))

    @commands.hybrid_command(name="blackjack", description="Play blackjack against the bot")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'")
    async def blackjack(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        bet = await self._take_bet(ctx, amount, "Blackjack bet")
        if bet is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        view = BlackjackView(ctx.author.id, ctx.guild.id, bet, settings['currency_symbol'])

        if is_blackjack(view.player_hand) or is_blackjack(view.dealer_hand):
            if is_blackjack(view.player_hand) and is_blackjack(view.dealer_hand):
                await db.add_coins(ctx.author.id, ctx.guild.id, bet, "Blackjack push")
                result_text = f"Both hands are blackjack. Your {settings['currency_symbol']} **{bet:,}** bet was returned."
            elif is_blackjack(view.player_hand):
                payout = int(bet * 2.5)
                await db.add_coins(ctx.author.id, ctx.guild.id, payout, "Blackjack natural")
                result_text = f"Blackjack. You received {settings['currency_symbol']} **{payout:,}**."
            else:
                result_text = f"Dealer blackjack. You lost {settings['currency_symbol']} **{bet:,}**."
            await ctx.send(embed=view.build_embed(reveal_dealer=True, result_text=result_text))
            return

        view.message = await ctx.send(embed=view.build_embed(), view=view)

    @commands.hybrid_command(name="crash", description="Cash out before the multiplier crashes")
    @commands.guild_only()
    @app_commands.describe(amount="Bet amount or 'all'")
    async def crash(self, ctx: commands.Context, amount: str):
        assert ctx.guild.id is not None
        bet = await self._take_bet(ctx, amount, "Crash bet")
        if bet is None:
            return
        settings = await db.get_economy_settings(ctx.guild.id)
        view = CrashView(ctx.author.id, ctx.guild.id, bet, settings['currency_symbol'])
        view.message = await ctx.send(embed=view.build_embed(), view=view)
        await view.start()

    @commands.hybrid_command(name="shop", description="Browse the economy shop")
    @commands.guild_only()
    async def shop(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        catalog = await self._get_shop_catalog(ctx.guild.id)
        lines = [self._shop_display_line(item, settings['currency_symbol']) for item in catalog.values()]
        embed = discord.Embed(
            title="🛒 Shop",
            description="Use `/buy <item_key>` to purchase an item.",
            color=discord.Color.blurple(),
        )
        if lines:
            embed.add_field(name="Available Items", value="\n\n".join(lines), inline=False)
        else:
            embed.description = "The shop is currently empty."
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy", description="Buy an item from the shop")
    @commands.guild_only()
    @app_commands.describe(item_key="Item key shown in /shop")
    async def buy(self, ctx: commands.Context, item_key: str):
        assert ctx.guild.id is not None
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        settings = await db.get_economy_settings(ctx.guild.id)
        key = clean_item_key(item_key)
        catalog = await self._get_shop_catalog(ctx.guild.id)
        item = catalog.get(key)
        if not item:
            await ctx.send("That item does not exist in the shop.", ephemeral=True)
            return

        success = await db.remove_coins(ctx.author.id, ctx.guild.id, item['price'], f"Shop purchase: {key}")
        if not success:
            await ctx.send("You do not have enough cash for that purchase.", ephemeral=True)
            return

        if item['item_type'] == "role":
            role = ctx.guild.get_role(item['role_id']) if item.get('role_id') else None
            if role is None:
                await db.add_coins(ctx.author.id, ctx.guild.id, item['price'], f"Refund for missing shop role: {key}")
                await ctx.send("That role item is misconfigured. Your coins were refunded.", ephemeral=True)
                return
            if role in ctx.author.roles:
                await db.add_coins(ctx.author.id, ctx.guild.id, item['price'], f"Refund for owned shop role: {key}")
                await ctx.send("You already own that role. Your coins were refunded.", ephemeral=True)
                return
            try:
                await ctx.author.add_roles(role, reason="Economy shop purchase")
            except discord.Forbidden:
                await db.add_coins(ctx.author.id, ctx.guild.id, item['price'], f"Refund for failed shop role: {key}")
                await ctx.send("I could not assign that role. Your coins were refunded.", ephemeral=True)
                return
            await ctx.send(f"✅ Purchased **{item['name']}** for {settings['currency_symbol']} **{item['price']:,}**.")
            return

        await db.add_inventory_item(ctx.author.id, ctx.guild.id, key, 1)
        await ctx.send(f"✅ Purchased **{item['name']}** for {settings['currency_symbol']} **{item['price']:,}**.")

    @commands.hybrid_command(name="inventory", description="View your inventory")
    @commands.guild_only()
    async def inventory(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        inventory_rows = await db.get_inventory(ctx.author.id, ctx.guild.id)
        active_boost = await db.get_active_xp_boost(ctx.author.id, ctx.guild.id)
        if not inventory_rows and not active_boost:
            await ctx.send("Your inventory is empty.", ephemeral=True)
            return

        embed = discord.Embed(title="🎒 Inventory", color=discord.Color.blurple())
        if inventory_rows:
            lines = []
            for row in inventory_rows:
                item = BUILTIN_SHOP_ITEMS.get(row['item_key'])
                name = item['name'] if item else row['item_key'].replace("_", " ").title()
                lines.append(f"**{name}** (`{row['item_key']}`) x{row['quantity']}")
            embed.add_field(name="Items", value="\n".join(lines), inline=False)
        if active_boost:
            embed.add_field(
                name="Active XP Boost",
                value=f"**{active_boost['multiplier']:.2f}x** until {format_cooldown(active_boost['expires_at'])}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="use", description="Use an item from your inventory")
    @commands.guild_only()
    @app_commands.describe(item_key="Item key from /inventory")
    async def use(self, ctx: commands.Context, item_key: str):
        assert ctx.guild.id is not None
        key = clean_item_key(item_key)
        item = BUILTIN_SHOP_ITEMS.get(key)
        if not item:
            await ctx.send("That item cannot be used.", ephemeral=True)
            return

        quantity = await db.get_inventory_quantity(ctx.author.id, ctx.guild.id, key)
        if quantity <= 0:
            await ctx.send("You do not own that item.", ephemeral=True)
            return

        if item['item_type'] == "shield":
            await ctx.send("Shields are passive. They are consumed automatically when someone tries to rob you.", ephemeral=True)
            return

        if item['item_type'] == "xp_boost":
            await db.remove_inventory_item(ctx.author.id, ctx.guild.id, key, 1)
            await db.activate_xp_boost(ctx.author.id, ctx.guild.id, item['boost_multiplier'], item['boost_hours'])
            boost = await db.get_active_xp_boost(ctx.author.id, ctx.guild.id)
            await ctx.send(f"✨ Activated **{item['boost_multiplier']:.1f}x XP** until {format_cooldown(boost['expires_at'])}.")
            return

        await ctx.send("That item cannot be used right now.", ephemeral=True)

    @commands.hybrid_command(name="richest", description="View the richest members on the server")
    @commands.guild_only()
    async def richest(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        settings = await db.get_economy_settings(ctx.guild.id)
        rows = await db.get_economy_leaderboard(ctx.guild.id, 10)
        if not rows:
            await ctx.send("Nobody has any coins yet.", ephemeral=True)
            return

        lines = []
        for index, row in enumerate(rows, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(index, f"**{index}.**")
            lines.append(f"{medal} <@{row['user_id']}> — {settings['currency_symbol']} **{row['cash'] + row['bank']:,}**")
        await ctx.send(embed=discord.Embed(title="💎 Richest Members", description="\n".join(lines), color=discord.Color.gold()))

    @shopadmin_group.command(name="addrole", description="Add a purchasable role to the shop")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @app_commands.describe(
        role="Role to sell",
        price="Purchase price",
        item_key="Unique key used with /buy",
        name="Display name in the shop",
        description="Item description",
    )
    async def shopadmin_addrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        price: int,
        item_key: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        assert ctx.guild.id is not None
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You need administrator permissions for this command.", ephemeral=True)
            return
        if price <= 0:
            await ctx.send("Price must be greater than zero.", ephemeral=True)
            return

        key = clean_item_key(item_key)
        if not key:
            await ctx.send("Please provide a valid item key.", ephemeral=True)
            return
        if key in BUILTIN_SHOP_ITEMS:
            await ctx.send("That item key is reserved by a built-in item.", ephemeral=True)
            return

        await db.upsert_shop_item(
            ctx.guild.id,
            key,
            name or role.name,
            description or f"Unlocks the {role.name} role.",
            price,
            "role",
            role_id=role.id,
        )
        await ctx.send(f"✅ Added role item `{key}` to the shop.", ephemeral=True)

    @shopadmin_group.command(name="remove", description="Remove a custom shop item")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def shopadmin_remove(self, ctx: commands.Context, item_key: str):
        assert ctx.guild.id is not None
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You need administrator permissions for this command.", ephemeral=True)
            return
        removed = await db.remove_shop_item(ctx.guild.id, clean_item_key(item_key))
        if removed:
            await ctx.send("✅ Shop item removed.", ephemeral=True)
        else:
            await ctx.send("That custom shop item does not exist.", ephemeral=True)

    @shopadmin_group.command(name="list", description="List custom shop items")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def shopadmin_list(self, ctx: commands.Context):
        assert ctx.guild.id is not None
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You need administrator permissions for this command.", ephemeral=True)
            return

        rows = await db.get_shop_items(ctx.guild.id)
        if not rows:
            await ctx.send("No custom shop items are configured.", ephemeral=True)
            return

        lines = [f"`{row['item_key']}` • {row['name']} • {row['price']:,}" for row in rows]
        await ctx.send("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
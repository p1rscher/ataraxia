# cogs/admin/announce.py
import discord
from discord.ext import commands
import logging
import asyncio

from core import database_pg as db

logger = logging.getLogger(__name__)

# ── Branding constants ──────────────────────────────────────────
ANNOUNCE_COLOR = 0x5865F2          # Discord blurple
MAINTENANCE_COLOR = 0xFEE75C       # Warning yellow
ANNOUNCEMENT_FOOTER = "Ataraxia • Bot Announcement"


class AnnounceConfirmView(discord.ui.View):
    """Confirmation view before broadcasting an announcement."""

    def __init__(self, author: discord.User):
        super().__init__(timeout=60)
        self.author = author
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    @discord.ui.button(label="Confirm & Broadcast", style=discord.ButtonStyle.green, emoji="📢")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()


class AnnounceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="announce", hidden=True)
    async def announce(self, ctx: commands.Context, *, message: str = None):
        """Broadcast an announcement to all servers with an announcement channel configured.

        Usage:
            Atx.announce <message>
            Atx.announce maintenance <message>   — uses a maintenance/warning style
        """

        # ── Owner check ────────────────────────────────────────
        if not await self.bot.is_owner(ctx.author):
            return

        if not message:
            embed = discord.Embed(
                title="📢 Announce — Usage",
                description=(
                    "**Send a standard announcement:**\n"
                    "`Atx.announce <message>`\n\n"
                    "**Send a maintenance notice:**\n"
                    "`Atx.announce maintenance <message>`\n\n"
                    "The announcement will be sent to every server that has "
                    "configured a bot announcement channel via `/botannouncements set`."
                ),
                color=ANNOUNCE_COLOR,
            )
            await ctx.send(embed=embed)
            return

        # ── Determine announcement type ────────────────────────
        is_maintenance = False
        if message.lower().startswith("maintenance "):
            is_maintenance = True
            message = message[len("maintenance "):]

        # ── Build the announcement embed ───────────────────────
        if is_maintenance:
            embed = discord.Embed(
                title="🔧 Maintenance Notice",
                description=message,
                color=MAINTENANCE_COLOR,
            )
            embed.set_footer(text=f"{ANNOUNCEMENT_FOOTER} • Maintenance")
        else:
            embed = discord.Embed(
                title="📢 Bot Announcement",
                description=message,
                color=ANNOUNCE_COLOR,
            )
            embed.set_footer(text=ANNOUNCEMENT_FOOTER)

        embed.timestamp = discord.utils.utcnow()

        # ── Fetch target channels ──────────────────────────────
        targets = await db.get_all_announcement_channels()

        if not targets:
            await ctx.send("⚠️ No servers have configured an announcement channel yet.")
            return

        # ── Preview + Confirm ──────────────────────────────────
        preview_embed = discord.Embed(
            title="📋 Announcement Preview",
            description=f"This will be sent to **{len(targets)}** server(s).",
            color=0x2F3136,
        )
        view = AnnounceConfirmView(ctx.author)
        preview_msg = await ctx.send(embeds=[preview_embed, embed], view=view)

        await view.wait()

        if view.value is None:
            await preview_msg.edit(content="⏰ Timed out — announcement cancelled.", view=None, embeds=[])
            return
        if not view.value:
            await preview_msg.edit(content="❌ Announcement cancelled.", view=None, embeds=[])
            return

        # ── Broadcast ──────────────────────────────────────────
        success = 0
        failed = 0

        status_msg = await ctx.send(f"📡 Broadcasting to {len(targets)} server(s)...")

        for target in targets:
            guild = self.bot.get_guild(target["guild_id"])
            if not guild:
                failed += 1
                continue

            channel = guild.get_channel(target["announcement_channel_id"])
            if not channel or not isinstance(channel, discord.TextChannel):
                failed += 1
                continue

            try:
                await channel.send(embed=embed)
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

            # Small delay to respect rate limits
            await asyncio.sleep(0.3)

        # ── Report results ─────────────────────────────────────
        result_embed = discord.Embed(
            title="✅ Announcement Broadcast Complete",
            description=(
                f"**Delivered:** {success}/{len(targets)} servers\n"
                f"**Failed:** {failed}/{len(targets)} servers"
            ),
            color=discord.Color.green() if failed == 0 else discord.Color.orange(),
        )
        await status_msg.edit(content=None, embed=result_embed)

        logger.info(
            f"Announcement broadcast by {ctx.author} — "
            f"{success} delivered, {failed} failed out of {len(targets)} targets"
        )


async def setup(bot):
    await bot.add_cog(AnnounceCog(bot))

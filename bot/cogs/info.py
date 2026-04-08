import discord
from discord.ext import commands
from discord import app_commands
import logging

try:
    from utils.embeds import get_guild_color
except ImportError:
    async def get_guild_color(guild_id: int, color_type: str = 'color_primary'):
        return discord.Color.blurple()

logger = logging.getLogger(__name__)

class CategorySelect(discord.ui.Select):
    def __init__(self, categories: list[str]):
        options = [
            discord.SelectOption(
                label=cat.replace("📁 ", "").split(" ", 1)[-1] if " " in cat else cat,
                value=cat,
                description=f"View commands for {cat}"
            )
            for cat in categories[:25]
        ]
        super().__init__(placeholder="Choose a command category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        self.view.current_category_idx = self.view.categories.index(selected_category)
        await self.view.update_message(interaction)

class CommandPaginator(discord.ui.View):
    def __init__(self, groups: dict, color: int, user_id: int):
        super().__init__(timeout=180)
        self.groups = groups
        self.categories = sorted(list(groups.keys()))
        self.color = color
        self.user_id = user_id
        
        # State: -1 means "Home Menu", 0+ means index of current category
        self.current_category_idx = -1
        
        # Initialize UI elements
        self.category_select = CategorySelect(self.categories)
        self.add_item(self.category_select)
        
        self.prev_button = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="c_prev")
        self.home_button = discord.ui.Button(label="🏠 Home", style=discord.ButtonStyle.success, custom_id="c_home")
        self.next_button = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="c_next")
        
        self.prev_button.callback = self.on_prev
        self.home_button.callback = self.on_home
        self.next_button.callback = self.on_next
        
        self.add_item(self.prev_button)
        self.add_item(self.home_button)
        self.add_item(self.next_button)
        
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
            return False
        return True

    def _update_buttons(self):
        if self.current_category_idx == -1:
            self.prev_button.disabled = True
            self.home_button.disabled = True
            self.next_button.disabled = True
            for opt in self.category_select.options:
                opt.default = False
        else:
            self.prev_button.disabled = (self.current_category_idx == 0)
            self.home_button.disabled = False
            self.next_button.disabled = (self.current_category_idx == len(self.categories) - 1)
            for i, opt in enumerate(self.category_select.options):
                opt.default = (i == self.current_category_idx)

    async def on_prev(self, interaction: discord.Interaction):
        self.current_category_idx -= 1
        await self.update_message(interaction)

    async def on_home(self, interaction: discord.Interaction):
        self.current_category_idx = -1
        await self.update_message(interaction)

    async def on_next(self, interaction: discord.Interaction):
        self.current_category_idx += 1
        await self.update_message(interaction)

    def build_embed(self) -> discord.Embed:
        total_commands = sum(len(cmds) for cmds in self.groups.values())
        
        if self.current_category_idx == -1:
            embed = discord.Embed(
                title="📜 Command Categories",
                description="Please select a category from the dropdown below to see its commands.",
                color=self.color
            )
            cats = "\n".join([f"**{cat}** ({len(self.groups[cat])} commands)" for cat in self.categories])
            embed.add_field(name="Available Categories", value=cats)
            embed.set_footer(text=f"Total Commands: {total_commands} | (P) = Premium | (P+) = Premium+")
            return embed
        
        cat_name = self.categories[self.current_category_idx]
        cmds = self.groups[cat_name]
        
        embed = discord.Embed(
            title=f"Commands: {cat_name}",
            description="Commands marked with **(P)** or **(P+)** require Premium.",
            color=self.color
        )
        
        current_val = ""
        field_count = 1
        for name, desc, is_p, is_p_plus in cmds:
            markers = " **(P+)**" if is_p_plus else " **(P)**" if is_p else ""
            cmd_text = f"`/{name}`{markers} - {desc}\n"
            
            if len(current_val) + len(cmd_text) > 1000:
                embed.add_field(name=f"Commands (Part {field_count})" if field_count > 1 else "Commands", value=current_val, inline=False)
                current_val = cmd_text
                field_count += 1
            else:
                current_val += cmd_text
                
        if current_val:
            embed.add_field(name=f"Commands (Part {field_count})" if field_count > 1 else "Commands", value=current_val, inline=False)
            
        embed.set_footer(text=f"Total: {total_commands} Cmds | Category {self.current_category_idx + 1}/{len(self.categories)} | (P) = Premium | (P+) = Premium+")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

class InfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _categorize_command(self, group_name: str, cmd_name: str) -> str:
        gn_lower = (group_name or "").lower()
        cn_lower = cmd_name.lower()
        full_cmd_name = f"{gn_lower} {cn_lower}".strip()
        
        # 1. Exact Subcommand Overrides
        overrides = {
            "voicelog set": "⚙️ Server Setup & Logs",
            "channel cleanup": "🛡️ Moderation",
            "voicelog clear": "📈 XP & Logging",
            "log clear": "📈 XP & Logging",
            "autorole clear": "🔐 Server Roles & Security"
        }
        
        if full_cmd_name in overrides:
            return overrides[full_cmd_name]

        # 2. General Logical Capabilities Mapping
        cats = {
            "🌸 Ataraxia": ["about", "hello", "info", "say"],
            "💎 Premium": ["premium"],
            "🤖 AI": ["ai"],
            "🧮 Math": ["math"],
            "🛡️ Moderation": ["ban", "kick", "mute", "timeout", "warn", "warnings", "delwarn", "clear", "purge", "unban", "unmute", "lock", "unlock", "slowmode", "nuke"],
            "📈 XP & Logging": ["xp", "xpadm", "xpmultiplier", "levelrole", "levellog", "voicexp-requirements", "level", "rank", "leaderboard"],
            "🎙️ Voice & Channels": ["channel", "tempvoice", "voicelog", "voice", "vctemp"],
            "💰 Economy & Shop": ["shopadmin", "shop", "economy", "pay", "balance", "daily", "work", "crime", "rob", "beg", "deposit", "withdraw"],
            "🎮 Fun & Games": ["counting", "game", "tictactoe", "8ball", "coinflip", "meme"],
            "🔐 Server Roles & Security": ["autorole", "reactionroles", "verification", "welcome", "parentrole", "verify", "roles"],
            "⚙️ Server Setup & Logs": ["serverstats", "log", "settings", "config", "setup", "logs", "modlog"],
            "🛠️ Utility & Misc": ["bump", "ping", "avatar", "userinfo", "serverinfo", "stats", "botinfo"]
        }
        
        # Exact match
        for cat, keywords in cats.items():
            if gn_lower in keywords or cn_lower in keywords:
                return cat
                
        # Substring match (ensure it's somewhat isolated)
        for cat, keywords in cats.items():
            for kw in keywords:
                if kw in gn_lower or kw in cn_lower:
                    return cat
                    
        if group_name and group_name.lower() != "general":
            return f"📁 {group_name.title()}"
            
        return "📌 General"

    @app_commands.command(name="info", description="List all available commands and premium features")
    async def commands_list(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            groups = {}
            for cmd in self.bot.tree.get_commands():
                if isinstance(cmd, app_commands.Group):
                    for sub_cmd in cmd.commands:
                        desc, is_p, is_p_plus = self._parse_description(sub_cmd.description)
                        command_string = f"{cmd.name} {sub_cmd.name}"
                        logical_cat = self._categorize_command(cmd.name, sub_cmd.name)
                        
                        if logical_cat not in groups:
                            groups[logical_cat] = []
                        groups[logical_cat].append((command_string, desc, is_p, is_p_plus))
                else:
                    desc, is_p, is_p_plus = self._parse_description(cmd.description)
                    command_string = cmd.name
                    logical_cat = self._categorize_command(None, cmd.name)
                    
                    if logical_cat not in groups:
                        groups[logical_cat] = []
                    groups[logical_cat].append((command_string, desc, is_p, is_p_plus))
            
            # Sort individual commands
            for cat in groups:
                groups[cat].sort(key=lambda x: x[0])

            if not groups:
                return await interaction.followup.send("No commands found.", ephemeral=True)
                
            color = await get_guild_color(interaction.guild_id if interaction.guild_id else 0)
            view = CommandPaginator(groups, color, interaction.user.id)
            
            await interaction.followup.send(embed=view.build_embed(), view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in info command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)

    def _parse_description(self, desc: str):
        is_p = False
        is_p_plus = False
        clean_desc = desc
        
        upper_desc = desc.upper()
        if "[PREMIUM+]" in upper_desc:
            is_p_plus = True
            clean_desc = "".join(desc.split("[PREMIUM+]")).strip()
            clean_desc = "".join(clean_desc.split("[Premium+]")).strip()
        elif "[PREMIUM]" in upper_desc:
            is_p = True
            clean_desc = "".join(desc.split("[PREMIUM]")).strip()
            clean_desc = "".join(clean_desc.split("[Premium]")).strip()
            
        return clean_desc, is_p, is_p_plus

async def setup(bot):
    await bot.add_cog(InfoCog(bot))

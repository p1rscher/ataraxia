import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone

try:
    from utils.embeds import get_guild_color
except ImportError:
    async def get_guild_color(guild_id: int, color_type: str = 'color_primary'):
        return discord.Color.blurple()

try:
    from core import database_pg as db
except ImportError:
    db = None

logger = logging.getLogger(__name__)

# --- UI Components ---

class CategorySelect(discord.ui.Select):
    """Dropdown for selecting command categories."""
    def __init__(self, categories: List[Tuple[str, str]]):
        options = [
            discord.SelectOption(
                label=display_name,
                value=cog_name,
                emoji=display_name.split(" ", 1)[0] if " " in display_name else None,
                description=f"View commands in {display_name}"
            )
            for cog_name, display_name in categories
        ]
        super().__init__(
            placeholder="Select a category to explore commands...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.switch_category(interaction, self.values[0])

class HelpView(discord.ui.View):
    """Main view for the interactive help menu."""
    def __init__(self, cog: 'HelpCog', user: discord.User, guild_id: int, color: discord.Color):
        super().__init__(timeout=600)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.color = color
        
        # State: 'home' or a Cog name
        self.current_page = 'home'
        
        # Fetch categorized commands
        self.categorized_commands = self.cog._get_all_commands()
        self.categories = self.cog._get_category_list(list(self.categorized_commands.keys()))
        
        # UI Elements
        self.select_menu = CategorySelect(self.categories)
        self.add_item(self.select_menu)
        
        # Buttons
        self.add_item(discord.ui.Button(label="Website", url="https://ataraxia.bot", row=2))
        self.add_item(discord.ui.Button(label="Support", url="https://discord.gg/fWPDEFRF87", row=2))
        self.add_item(discord.ui.Button(label="GitHub", url="https://github.com/p1rscher/ataraxia", row=2))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This help menu is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 'home'
        await self.update_view(interaction)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.danger, row=3)
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Removes the help menu view and updates the embed."""
        await interaction.response.edit_message(
            content="🌸 Help menu closed. Have a wonderful day!",
            embed=None,
            view=None
        )
        self.stop()

    async def switch_category(self, interaction: discord.Interaction, cog_name: str):
        self.current_page = cog_name
        await self.update_view(interaction)

    async def update_view(self, interaction: discord.Interaction):
        embed = await self.cog._build_embed(self.current_page, self.user, self.guild_id, self.color)
        # Update select menu default
        for option in self.select_menu.options:
            option.default = (option.value == self.current_page)
            
        await interaction.response.edit_message(embed=embed, view=self)

# --- Help Cog ---

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Map Internal Cog Names to Display Names + Emojis
        self.cog_map = {
            "AdminStats": "📈 Admin Stats",
            "BumpReminder": "🔔 Bump Reminder",
            "Insights": "📊 Server Insights",
            "Shutdown": "🛑 System Control",
            "Economy": "💰 Economy & Wealth",
            "Counting": "🎮 Games & Counting",
            "Fun": "🎮 Games & Fun",
            "Hello": "🌸 General",
            "LevelRoles": "📈 Levels & XP",
            "VoiceXPRequirements": "📈 Levels & XP",
            "XPSettings": "📈 Levels & XP",
            "CleanupChannel": "🛡️ Moderation",
            "Moderation": "🛡️ Moderation",
            "ParentRoles": "🛡️ Moderation",
            "Verification": "🛡️ Verification",
            "Premium": "💎 Premium Status",
            "Autorole": "🔐 Security & Roles",
            "CustomRole": "🔐 Security & Roles",
            "LogConfig": "🔐 Logging",
            "ReactionRoles": "🔐 Interaction Panels",
            "ServerStats": "📊 Server Tools",
            "Settings": "⚙️ System Settings",
            "TempVoice": "🎙️ Voice Tools",
            "Ticket": "🎫 Ticket System",
            "Welcome": "👋 Welcome Center",
            "About": "🌸 About Ataraxia",
            "AI": "🤖 Artificial Intelligence",
            "EmbedBuilder": "🎨 Design Tools",
            "Math": "🧮 Advanced Math",
            "Say": "🌸 General",
            "General": "📌 General Commands"
        }

    def _get_category_list(self, available_cogs: List[str]) -> List[Tuple[str, str]]:
        """Returns sorted list of (internal_name, display_name) tuples."""
        cats = []
        for cog_name in available_cogs:
            display = self.cog_map.get(cog_name, f"📁 {cog_name}")
            cats.append((cog_name, display))
        
        # Sort by display name (emoji first)
        return sorted(cats, key=lambda x: x[1])

    def _get_all_commands(self) -> Dict[str, List[app_commands.Command]]:
        """Groups all bot commands by Cog."""
        groups = {}
        
        # 1. Process Slash Commands from Tree
        for cmd in self.bot.tree.get_commands():
            if isinstance(cmd, app_commands.Group):
                # We prioritize the Cog that owns the group
                cog_name = cmd.module.split(".")[-1].title() if hasattr(cmd, "module") else "General"
                if cog_name not in groups: groups[cog_name] = []
                
                for sub in cmd.commands:
                    groups[cog_name].append(sub)
            else:
                # Top level slash command
                cog_name = "General"
                # Check which cog owns it
                for c_name, c_obj in self.bot.cogs.items():
                    if cmd.name in [a.name for a in c_obj.get_app_commands()]:
                        cog_name = c_name
                        break
                
                if cog_name not in groups: groups[cog_name] = []
                groups[cog_name].append(cmd)

        return groups

    async def _build_embed(self, page: str, user: discord.User, guild_id: int, color: discord.Color) -> discord.Embed:
        if page == 'home':
            return await self._build_home_embed(user, guild_id, color)
        else:
            return self._build_category_embed(page, color)

    async def _build_home_embed(self, user: discord.User, guild_id: int, color: discord.Color) -> discord.Embed:
        embed = discord.Embed(
            title="🌸 Ataraxia Command Center",
            description=(
                "Welcome to the Ataraxia Help Menu! \n"
                "Use the dropdown below to explore specific command categories.\n\n"
                "**Quick Navigation Guide:**\n"
                "• 🏠 Returns you to this dashboard.\n"
                "• Select a category for detailed command usage.\n"
                "• Use `/commandname` or `Atx.commandname`."
            ),
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Premium Status
        tier = "Free"
        if db:
            tier_raw = await db.get_user_premium_tier(user.id)
            tier = tier_raw.replace("_", " ").title() if tier_raw else "Free"
            
        status_emoji = "💎" if tier != "Free" else "👤"
        embed.add_field(
            name=f"{status_emoji} Your Account Status",
            value=f"Tier: **{tier}**\nThank you for choosing Ataraxia!",
            inline=True
        )

        # Bot Stats
        total_cmds = len(self.bot.tree.get_commands())
        embed.add_field(
            name="🤖 Global Statistics",
            value=f"Servers: **{len(self.bot.guilds):,}**\nCommands: **{total_cmds}**",
            inline=True
        )

        embed.set_footer(text="Modernizing Discord Management | v2.1.0")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        return embed

    def _build_category_embed(self, cog_name: str, color: discord.Color) -> discord.Embed:
        display_name = self.cog_map.get(cog_name, f"📁 {cog_name}")
        embed = discord.Embed(
            title=f"{display_name}",
            description=f"Showing all commands in the **{cog_name}** module.",
            color=color
        )
        
        all_cmds = self._get_all_commands()
        cmds = all_cmds.get(cog_name, [])
        
        if not cmds:
            embed.description = "No commands found in this category."
            return embed

        cmd_list = []
        for cmd in cmds:
            desc = cmd.description[:100] if cmd.description else "No description available."
            
            # Premium marking
            prefix = ""
            if "[PREMIUM]" in desc.upper():
                prefix = "💎 "
                desc = desc.replace("[PREMIUM]", "").replace("[premium]", "").strip()
            if "[PREMIUM+]" in desc.upper():
                prefix = "✨ "
                desc = desc.replace("[PREMIUM+]", "").replace("[premium+]", "").strip()

            cmd_list.append(f"**{prefix}`/{cmd.name}`**\n╰ {desc}")

        # Discord field limit is 1024. If list is too long, we split into fields.
        current_chunk = ""
        for item in cmd_list:
            if len(current_chunk) + len(item) > 900:
                embed.add_field(name="Commands", value=current_chunk, inline=False)
                current_chunk = item + "\n"
            else:
                current_chunk += item + "\n"
        
        if current_chunk:
            embed.add_field(name="Commands", value=current_chunk, inline=False)

        embed.set_footer(text=f"Navigate using the menu below • {len(cmds)} commands")
        return embed

    @commands.hybrid_command(name="help", description="Access the interactive command help menu")
    async def help_command(self, ctx: commands.Context):
        """Standard help command with UI buttons."""
        color = await get_guild_color(ctx.guild.id if ctx.guild else None)
        view = HelpView(self, ctx.author, ctx.guild.id if ctx.guild else 0, color)
        
        embed = await self._build_embed('home', ctx.author, ctx.guild.id if ctx.guild else 0, color)
        await ctx.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))

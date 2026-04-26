import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color, reload_guild_persistent_embeds

logger = logging.getLogger(__name__)

COLOR_TYPES = {
    'global': 'color_primary',
    'welcome': 'color_welcome',
    'level_up': 'color_level_up',
    'success': 'color_success',
    'counting': 'color_counting',
    'verification': 'color_verification',
    'ticket': 'color_ticket',
}

COLOR_DESCRIPTIONS = {
    'global': 'Main color for all bot embeds',
    'welcome': 'Color for welcome messages',
    'level_up': 'Color for level-up notifications',
    'success': 'Color for success/confirmation messages',
    'counting': 'Color for counting game embeds',
    'verification': 'Color for verification messages',
    'ticket': 'Color for ticket panels',
}


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="settings",
        description="Server settings and customization"
    )
    async def settings_group(self, ctx: commands.Context):
        pass

    @settings_group.group(
        name="color",
        description="Customize embed colors"
    )
    async def color_group(self, ctx: commands.Context):
        pass

    @settings_group.group(
        name="prefix",
        description="Customize the bot prefix (Premium)"
    )
    async def prefix_group(self, ctx: commands.Context):
        pass

    async def _has_premium_access(self, user: discord.abc.User) -> bool:
        """Check if the user has premium or is the bot owner."""
        if await self.bot.is_owner(user):
            return True
        tier = await db.get_user_premium_tier(user.id)
        return tier in ("premium", "premium_plus")

    @color_group.command(name="set", description="Set a custom embed color for this server")
    @app_commands.describe(
        hex_color="Hex color code (e.g. #FF5733 or FF5733)",
        type="Optional: Specific type to customize (default: Global)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Global (Used for everything)", value="global"),
        app_commands.Choice(name="Welcome messages", value="welcome"),
        app_commands.Choice(name="Level up notifications", value="level_up"),
        app_commands.Choice(name="Success messages", value="success"),
        app_commands.Choice(name="Counting game", value="counting"),
        app_commands.Choice(name="Verification messages", value="verification"),
        app_commands.Choice(name="Ticket panels", value="ticket"),
    ])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_set(self, ctx: commands.Context, hex_color: str, type: str = "global"):
        """Set a custom color"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        hex_clean = hex_color.lstrip('#')
        if len(hex_clean) != 6:
            await ctx.send("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return
        try:
            color_int = int(hex_clean, 16)
        except ValueError:
            await ctx.send("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return

        color_type = COLOR_TYPES[type]
        await db.set_guild_color(ctx.guild.id, color_type, color_int)

        embed = discord.Embed(
            description=f"✅ **{type.title()}** color updated!",
            color=discord.Color(color_int)
        )
        embed.add_field(name="Color", value=f"`#{hex_clean.upper()}`")
        if type == "global":
            embed.set_footer(text="This color will now be used for all bot embeds by default.")
        
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} set {color_type} to #{hex_clean.upper()}")
        
        # Reload all persistent embeds to apply the new color
        await reload_guild_persistent_embeds(self.bot, ctx.guild.id)

    @color_group.command(name="view", description="View current embed colors for this server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_view(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        colors = await db.get_guild_colors(ctx.guild.id)
        defaults = db.DEFAULT_COLORS
        primary_color = await get_guild_color(ctx.guild.id)

        embed = discord.Embed(
            title="🎨 Server Embed Colors", 
            description="If a color is not set, it will automatically follow the **Global** color.",
            color=primary_color
        )
        
        for key, col_key in COLOR_TYPES.items():
            val = colors.get(col_key, defaults[col_key])
            is_custom = val != defaults[col_key]
            
            status = ""
            if key != 'global' and not is_custom:
                status = " *(following Global)*"
            elif is_custom:
                status = " *(customized)*"
            else:
                status = " *(customized)*" if val != defaults['color_primary'] else " *(default)*"

            embed.add_field(
                name=f"{key.replace('_', ' ').title()}{status}",
                value=f"`#{val:06X}` - {COLOR_DESCRIPTIONS[key]}",
                inline=False
            )
        await ctx.send(embed=embed, ephemeral=True)

    @color_group.command(name="reset", description="Reset all embed colors to defaults")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_reset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.reset_guild_colors(ctx.guild.id)
        await ctx.send("✅ All embed colors reset to defaults.", ephemeral=True)
        
        # Reload all persistent embeds
        await reload_guild_persistent_embeds(self.bot, ctx.guild.id)

    # ──────────────────────────────────────────────────────
    # /settings prefix set / view / reset  (Premium)
    # ──────────────────────────────────────────────────────

    @prefix_group.command(name="set", description="Set a custom prefix for this server (Premium)")
    @app_commands.describe(prefix="The new prefix (1-10 characters, e.g. '!' or 'mybot.')")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix_set(self, ctx: commands.Context, prefix: str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        if not await self._has_premium_access(ctx.author):
            await ctx.send(
                "❌ Custom prefixes are a **Premium** feature. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        prefix = prefix.strip()
        if not prefix or len(prefix) > 10:
            await ctx.send(
                "❌ Prefix must be between **1** and **10** characters.",
                ephemeral=True,
            )
            return

        await db.set_guild_prefix(ctx.guild.id, prefix)

        # Update the in-memory cache so the change takes effect immediately
        import main as _main
        _main._prefix_cache[ctx.guild.id] = prefix

        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(
            title="✅ Prefix Updated",
            description=f"The bot prefix for this server is now `{prefix}`",
            color=color,
        )
        embed.add_field(name="Example", value=f"`{prefix}warn @user reason`", inline=False)
        embed.set_footer(text="The default Atx. prefix will no longer work in this server.")
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} set custom prefix to '{prefix}'")

    @prefix_group.command(name="view", description="View the current prefix for this server")
    @commands.guild_only()
    async def prefix_view(self, ctx: commands.Context):
        custom = await db.get_guild_prefix(ctx.guild.id)
        color = await get_guild_color(ctx.guild.id)

        embed = discord.Embed(title="🔤 Current Prefix", color=color)
        if custom:
            embed.description = f"This server uses a custom prefix: `{custom}`"
            embed.add_field(name="Example", value=f"`{custom}warn @user reason`", inline=False)
        else:
            embed.description = "This server uses the default prefix: `Atx.`"
            embed.add_field(name="Example", value="`Atx.warn @user reason`", inline=False)
        embed.set_footer(text="You can always use @mention as a prefix too.")
        await ctx.send(embed=embed, ephemeral=True)

    @prefix_group.command(name="reset", description="Reset the prefix to the default (Atx.)")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix_reset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.clear_guild_prefix(ctx.guild.id)

        # Update the in-memory cache
        import main as _main
        _main._prefix_cache[ctx.guild.id] = _main.DEFAULT_PREFIX

        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(
            title="✅ Prefix Reset",
            description="The bot prefix has been reset to the default: `Atx.`",
            color=color,
        )
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} reset prefix to default")


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))


import discord
from discord.ext import commands
from discord import app_commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

COLOR_TYPES = {
    'primary': 'color_primary',
    'welcome': 'color_welcome',
    'level_up': 'color_level_up',
    'success': 'color_success',
    'counting': 'color_counting',
}

COLOR_DESCRIPTIONS = {
    'primary': 'Main color for info, lists and general embeds',
    'welcome': 'Color for welcome messages',
    'level_up': 'Color for level-up notifications',
    'success': 'Color for success/confirmation embeds',
    'counting': 'Color for counting game embeds',
}


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    settings_group = app_commands.Group(
        name="settings",
        description="Server settings and customization"
    )

    color_group = app_commands.Group(
        name="color",
        description="Customize embed colors",
        parent=settings_group
    )

    prefix_group = app_commands.Group(
        name="prefix",
        description="Customize the bot prefix (Premium)",
        parent=settings_group
    )

    async def _has_premium_access(self, user: discord.abc.User) -> bool:
        """Check if the user has premium or is the bot owner."""
        if await self.bot.is_owner(user):
            return True
        tier = await db.get_user_premium_tier(user.id)
        return tier in ("premium", "premium_plus")

    @color_group.command(name="set", description="Set a custom embed color for this server")
    @app_commands.describe(
        type="The embed type to customize",
        hex_color="Hex color code (e.g. #FF5733 or FF5733)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Primary (info, lists, general)", value="primary"),
        app_commands.Choice(name="Welcome message", value="welcome"),
        app_commands.Choice(name="Level up notification", value="level_up"),
        app_commands.Choice(name="Success / confirmation", value="success"),
        app_commands.Choice(name="Counting game", value="counting"),
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def color_set(self, ctx: discord.Interaction, type: str, hex_color: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        hex_clean = hex_color.lstrip('#')
        if len(hex_clean) != 6:
            await ctx.response.send_message("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return
        try:
            color_int = int(hex_clean, 16)
        except ValueError:
            await ctx.response.send_message("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return

        color_type = COLOR_TYPES[type]
        await db.set_guild_color(ctx.guild_id, color_type, color_int)

        embed = discord.Embed(
            description=f"✅ **{type.replace('_', ' ').title()}** color updated!",
            color=discord.Color(color_int)
        )
        embed.add_field(name="Color", value=f"`#{hex_clean.upper()}`")
        await ctx.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild_id} set {color_type} to #{hex_clean.upper()}")

    @color_group.command(name="view", description="View current embed colors for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def color_view(self, ctx: discord.Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        colors = await db.get_guild_colors(ctx.guild_id)
        primary_color = await get_guild_color(ctx.guild_id, 'color_primary')

        embed = discord.Embed(title="🎨 Embed Colors", color=primary_color)
        for key, col_key in COLOR_TYPES.items():
            val = colors.get(col_key, db.DEFAULT_COLORS[col_key])
            embed.add_field(
                name=f"{key.replace('_', ' ').title()}",
                value=f"`#{val:06X}`\n{COLOR_DESCRIPTIONS[key]}",
                inline=False
            )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @color_group.command(name="reset", description="Reset all embed colors to defaults")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def color_reset(self, ctx: discord.Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.reset_guild_colors(ctx.guild_id)
        await ctx.response.send_message("✅ All embed colors reset to defaults.", ephemeral=True)

    # ──────────────────────────────────────────────────────
    # /settings prefix set / view / reset  (Premium)
    # ──────────────────────────────────────────────────────

    @prefix_group.command(name="set", description="Set a custom prefix for this server (Premium)")
    @app_commands.describe(prefix="The new prefix (1-10 characters, e.g. '!' or 'mybot.')")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def prefix_set(self, ctx: discord.Interaction, prefix: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        if not await self._has_premium_access(ctx.user):
            await ctx.response.send_message(
                "❌ Custom prefixes are a **Premium** feature. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        prefix = prefix.strip()
        if not prefix or len(prefix) > 10:
            await ctx.response.send_message(
                "❌ Prefix must be between **1** and **10** characters.",
                ephemeral=True,
            )
            return

        await db.set_guild_prefix(ctx.guild_id, prefix)

        # Update the in-memory cache so the change takes effect immediately
        import main as _main
        _main._prefix_cache[ctx.guild_id] = prefix

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(
            title="✅ Prefix Updated",
            description=f"The bot prefix for this server is now `{prefix}`",
            color=color,
        )
        embed.add_field(name="Example", value=f"`{prefix}warn @user reason`", inline=False)
        embed.set_footer(text="The default Atx. prefix will no longer work in this server.")
        await ctx.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild_id} set custom prefix to '{prefix}'")

    @prefix_group.command(name="view", description="View the current prefix for this server")
    @app_commands.guild_only()
    async def prefix_view(self, ctx: discord.Interaction):
        custom = await db.get_guild_prefix(ctx.guild_id)
        color = await get_guild_color(ctx.guild_id)

        embed = discord.Embed(title="🔤 Current Prefix", color=color)
        if custom:
            embed.description = f"This server uses a custom prefix: `{custom}`"
            embed.add_field(name="Example", value=f"`{custom}warn @user reason`", inline=False)
        else:
            embed.description = "This server uses the default prefix: `Atx.`"
            embed.add_field(name="Example", value="`Atx.warn @user reason`", inline=False)
        embed.set_footer(text="You can always use @mention as a prefix too.")
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @prefix_group.command(name="reset", description="Reset the prefix to the default (Atx.)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def prefix_reset(self, ctx: discord.Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.clear_guild_prefix(ctx.guild_id)

        # Update the in-memory cache
        import main as _main
        _main._prefix_cache[ctx.guild_id] = _main.DEFAULT_PREFIX

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(
            title="✅ Prefix Reset",
            description="The bot prefix has been reset to the default: `Atx.`",
            color=color,
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild_id} reset prefix to default")


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))


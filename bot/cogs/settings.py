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


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))

import discord
from discord.ext import commands
from discord import app_commands
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    welcome_group = app_commands.Group(
        name="welcome",
        description="Configure the welcome message for new members"
    )

    @welcome_group.command(name="set", description="Set the welcome message for new members")
    @app_commands.describe(
        channel="The channel where the welcome message will be sent",
        message="The welcome message text. Use {user} to mention the new member and {server} for the server name."
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def welcome_set(self, ctx: discord.Interaction, channel: discord.TextChannel, message: str):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.set_welcome_message(ctx.guild_id, channel.id, message)
        await ctx.response.send_message(
            f"✅ Welcome message set!\n**Channel:** {channel.mention}\n**Message:** {message}",
            ephemeral=True
        )
        logger.info(f"Welcome message set for guild {ctx.guild_id} in channel {channel.id}")

    @welcome_group.command(name="show", description="Show the current welcome message configuration")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def welcome_show(self, ctx: discord.Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        settings = await db.get_welcome_message(ctx.guild_id)
        if not settings:
            await ctx.response.send_message("ℹ️ No welcome message configured for this server.", ephemeral=True)
            return

        channel = ctx.guild.get_channel(settings['channel_id'])
        channel_mention = channel.mention if channel else f"*(deleted channel, ID: {settings['channel_id']})*"
        await ctx.response.send_message(
            f"**Welcome message configuration:**\n**Channel:** {channel_mention}\n**Message:** {settings['message']}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))

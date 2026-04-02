# cogs/log_config.py
import discord
from discord.ext import commands
from discord import app_commands
from core import database_pg as db

class LogConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    log_group = app_commands.Group(name="log", description="Manage message edit/delete logging")

    @log_group.command(name="set", description="Set the log channel for message edits/deletes")
    @app_commands.describe(channel="The channel where logs will be sent")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setlog(self, ctx: discord.Interaction, channel: discord.TextChannel):
        await db.set_log_channel(ctx.guild.id, channel.id)
        await ctx.response.send_message(f"✅ Edit/Delete logs will now be sent to {channel.mention}", ephemeral=True)

    @log_group.command(name="clear", description="Remove the log channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def clearlog(self, ctx: discord.Interaction):
        await db.clear_log_channel(ctx.guild.id)
        await ctx.response.send_message("✅ Log channel removed. Logs will use the original channel as fallback.", ephemeral=True)

    voice_log_group = app_commands.Group(name="voicelog", description="Manage voice channel logging")

    @voice_log_group.command(name="set", description="Set the log channel for voice channel activity")
    @app_commands.describe(channel="The channel where voice logs will be sent")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setvoicelog(self, ctx: discord.Interaction, channel: discord.TextChannel):
        await db.set_voice_log_channel(ctx.guild.id, channel.id)
        await ctx.response.send_message(f"✅ Voice logs will now be sent to {channel.mention}", ephemeral=True)

    @voice_log_group.command(name="clear", description="Remove the voice log channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def clearvoicelog(self, ctx: discord.Interaction):
        await db.remove_voice_log_channel(ctx.guild.id)
        await ctx.response.send_message("✅ Voice log channel removed.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LogConfigCog(bot))

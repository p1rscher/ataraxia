# cogs/log_disable.py
import discord
from discord.ext import commands
from discord import app_commands
from core import database_pg as db

class LogDisableCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="disablelog", description="Disable a specific type of logging")
    @app_commands.describe(log_type="The type of log to disable")
    @app_commands.choices(log_type=[
        app_commands.Choice(name="Message Logs (Edits/Deletes)", value="message"),
        app_commands.Choice(name="Voice Logs", value="voice"),
        app_commands.Choice(name="Level Up Logs", value="level")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def disablelog(self, interaction: discord.Interaction, log_type: app_commands.Choice[str]):
        if log_type.value == "message":
            await db.clear_log_channel(interaction.guild.id)
            message = "✅ **Message Logs (Edits/Deletes)** have been disabled."
        elif log_type.value == "voice":
            await db.remove_voice_log_channel(interaction.guild.id)
            message = "✅ **Voice Logs** have been disabled."
        elif log_type.value == "level":
            await db.remove_level_log_channel(interaction.guild.id)
            message = "✅ **Level Up Logs** have been disabled."
        else:
            message = "❌ Invalid log type selected."
            
        await interaction.response.send_message(message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LogDisableCog(bot))

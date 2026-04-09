import discord
from discord import app_commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color


LOG_TYPE_CHOICES = [
    app_commands.Choice(name="Message Logs", value="message"),
    app_commands.Choice(name="Say Logs", value="say"),
    app_commands.Choice(name="Voice Logs", value="voice"),
    app_commands.Choice(name="Level Logs", value="level"),
]


class LogConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    log_group = app_commands.Group(name="log", description="Manage all log channels")

    async def _require_admin(self, ctx: discord.Interaction) -> bool:
        assert isinstance(ctx.user, discord.Member)
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return False
        return True

    async def _channel_display(self, guild: discord.Guild, channel_id: int | None) -> str:
        if channel_id == 0:
            return "Disabled everywhere"
        if not channel_id:
            return "Not configured"
        channel = guild.get_channel(channel_id)
        if channel:
            return channel.mention
        return f"Missing channel (`{channel_id}`)"

    @log_group.command(name="set", description="Set a log channel for any log type")
    @app_commands.describe(type="Which log type to configure", channel="Channel where logs should be sent")
    @app_commands.choices(type=LOG_TYPE_CHOICES)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_log(self, ctx: discord.Interaction, type: app_commands.Choice[str], channel: discord.TextChannel):
        assert ctx.guild is not None
        assert ctx.guild_id is not None
        if not await self._require_admin(ctx):
            return

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.response.send_message(
                f"❌ I do not have permission to send messages in {channel.mention}.",
                ephemeral=True,
            )
            return

        if type.value == "message":
            await db.set_log_channel(ctx.guild_id, channel.id)
            description = f"Message edit/delete logs will now be sent to {channel.mention}."
        elif type.value == "say":
            await db.set_say_log_channel(ctx.guild_id, channel.id)
            description = f"/say moderation logs will now be sent to {channel.mention}."
        elif type.value == "voice":
            await db.set_voice_log_channel(ctx.guild_id, channel.id)
            description = f"Voice activity logs will now be sent to {channel.mention}."
        else:
            await db.set_level_log_channel(ctx.guild_id, channel.id)
            description = f"Level-up logs will now be sent to {channel.mention}."

        embed = discord.Embed(
            title="✅ Log Channel Updated",
            description=description,
            color=await get_guild_color(ctx.guild_id),
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @log_group.command(name="clear", description="Clear a configured log channel")
    @app_commands.describe(type="Which log type to clear")
    @app_commands.choices(type=LOG_TYPE_CHOICES)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def clear_log(self, ctx: discord.Interaction, type: app_commands.Choice[str]):
        assert ctx.guild_id is not None
        if not await self._require_admin(ctx):
            return

        if type.value == "message":
            await db.clear_log_channel(ctx.guild_id)
            description = "Message edit/delete logs have been disabled."
        elif type.value == "say":
            await db.clear_say_log_channel(ctx.guild_id)
            description = "/say moderation logs have been disabled."
        elif type.value == "voice":
            await db.remove_voice_log_channel(ctx.guild_id)
            description = "Voice activity logs have been disabled."
        else:
            await db.remove_level_log_channel(ctx.guild_id)
            description = "Dedicated level log channel removed. Level-ups will fall back to the XP source channel."

        embed = discord.Embed(
            title="✅ Log Setting Cleared",
            description=description,
            color=await get_guild_color(ctx.guild_id),
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @log_group.command(name="disable", description="Explicitly disable a log type")
    @app_commands.describe(type="Which log type to disable")
    @app_commands.choices(type=LOG_TYPE_CHOICES)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def disable_log(self, ctx: discord.Interaction, type: app_commands.Choice[str]):
        assert ctx.guild_id is not None
        if not await self._require_admin(ctx):
            return

        if type.value == "message":
            await db.clear_log_channel(ctx.guild_id)
            description = "Message edit/delete logs have been disabled."
        elif type.value == "say":
            await db.clear_say_log_channel(ctx.guild_id)
            description = "/say moderation logs have been disabled."
        elif type.value == "voice":
            await db.remove_voice_log_channel(ctx.guild_id)
            description = "Voice activity logs have been disabled."
        else:
            await db.disable_level_log_channel(ctx.guild_id)
            description = "Level-up logs are now disabled everywhere."

        embed = discord.Embed(
            title="✅ Log Type Disabled",
            description=description,
            color=await get_guild_color(ctx.guild_id),
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @log_group.command(name="status", description="View all current log settings")
    @app_commands.guild_only()
    async def log_status(self, ctx: discord.Interaction):
        assert ctx.guild is not None
        assert ctx.guild_id is not None

        message_log_channel_id = await db.get_log_channel_id(ctx.guild_id)
        say_log_channel_id = await db.get_say_log_channel_id(ctx.guild_id)
        voice_log_channel_id = await db.get_voice_log_channel_id(ctx.guild_id)
        level_log_channel_id = await db.get_level_log_channel_id(ctx.guild_id)

        embed = discord.Embed(
            title="📋 Log Status",
            color=await get_guild_color(ctx.guild_id),
        )
        embed.add_field(
            name="Message Logs",
            value=(
                f"{await self._channel_display(ctx.guild, message_log_channel_id)}\n"
                "Covers message edits and deletes."
            ),
            inline=False,
        )
        embed.add_field(
            name="Say Logs",
            value=(
                f"{await self._channel_display(ctx.guild, say_log_channel_id)}\n"
                "Covers /say moderation logs only."
            ),
            inline=False,
        )
        embed.add_field(
            name="Voice Logs",
            value=await self._channel_display(ctx.guild, voice_log_channel_id),
            inline=False,
        )
        embed.add_field(
            name="Level Logs",
            value=(
                "Falls back to the XP source channel"
                if level_log_channel_id is None
                else await self._channel_display(ctx.guild, level_log_channel_id)
            ),
            inline=False,
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LogConfigCog(bot))
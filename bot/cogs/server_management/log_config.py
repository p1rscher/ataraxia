import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color


LOG_TYPE_CHOICES = [
    app_commands.Choice(name="Message Logs", value="message"),
    app_commands.Choice(name="Say Logs", value="say"),
    app_commands.Choice(name="Voice Logs", value="voice"),
    app_commands.Choice(name="Level Logs", value="level"),
    app_commands.Choice(name="Moderation Logs", value="moderation"),
    app_commands.Choice(name="User Traffic Logs", value="traffic"),
    app_commands.Choice(name="Ticket Logs", value="ticket"),
]


class LogConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="log", description="Manage all log channels")
    async def log_group(self, ctx: commands.Context):
        pass

    async def _require_admin(self, ctx: commands.Context) -> bool:
        assert isinstance(ctx.author, discord.Member)
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions for this command.", ephemeral=True)
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
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_log(self, ctx: commands.Context, type: app_commands.Choice[str], channel: discord.TextChannel):
        assert ctx.guild is not None
        assert ctx.guild.id is not None
        if not await self._require_admin(ctx):
            return

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(
                f"❌ I do not have permission to send messages in {channel.mention}.",
                ephemeral=True,
            )
            return

        if type.value == "message":
            await db.set_log_channel(ctx.guild.id, channel.id)
            description = f"Message edit/delete logs will now be sent to {channel.mention}."
        elif type.value == "say":
            await db.set_say_log_channel(ctx.guild.id, channel.id)
            description = f"/say moderation logs will now be sent to {channel.mention}."
        elif type.value == "voice":
            await db.set_voice_log_channel(ctx.guild.id, channel.id)
            description = f"Voice activity logs will now be sent to {channel.mention}."
        elif type.value == "moderation":
            await db.set_mod_log_channel(ctx.guild.id, channel.id)
            description = f"Moderation action logs will now be sent to {channel.mention}."
        elif type.value == "traffic":
            await db.set_traffic_log_channel(ctx.guild.id, channel.id)
            description = f"User traffic logs (joins/leaves) will now be sent to {channel.mention}."
        elif type.value == "ticket":
            await db.set_ticket_log_channel(ctx.guild.id, channel.id)
            description = f"Ticket logs (transcripts & closure) will now be sent to {channel.mention}."
        else:
            await db.set_level_log_channel(ctx.guild.id, channel.id)
            description = f"Level-up logs will now be sent to {channel.mention}."

        embed = discord.Embed(
            title="✅ Log Channel Updated",
            description=description,
            color=await get_guild_color(ctx.guild.id),
        )
        await ctx.send(embed=embed, ephemeral=True)

    @log_group.command(name="clear", description="Clear a configured log channel")
    @app_commands.describe(type="Which log type to clear")
    @app_commands.choices(type=LOG_TYPE_CHOICES)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def clear_log(self, ctx: commands.Context, type: app_commands.Choice[str]):
        assert ctx.guild.id is not None
        if not await self._require_admin(ctx):
            return

        if type.value == "message":
            await db.clear_log_channel(ctx.guild.id)
            description = "Message edit/delete logs have been disabled."
        elif type.value == "say":
            await db.clear_say_log_channel(ctx.guild.id)
            description = "/say moderation logs have been disabled."
        elif type.value == "voice":
            await db.remove_voice_log_channel(ctx.guild.id)
            description = "Voice activity logs have been disabled."
        elif type.value == "moderation":
            await db.clear_mod_log_channel(ctx.guild.id)
            description = "Moderation action logs have been disabled."
        elif type.value == "traffic":
            await db.clear_traffic_log_channel(ctx.guild.id)
            description = "User traffic logs have been disabled."
        elif type.value == "ticket":
            await db.clear_ticket_log_channel(ctx.guild.id)
            description = "Ticket logs have been disabled."
        else:
            await db.remove_level_log_channel(ctx.guild.id)
            description = "Dedicated level log channel removed. Level-ups will fall back to the XP source channel."

        embed = discord.Embed(
            title="✅ Log Setting Cleared",
            description=description,
            color=await get_guild_color(ctx.guild.id),
        )
        await ctx.send(embed=embed, ephemeral=True)

    @log_group.command(name="disable", description="Explicitly disable a log type")
    @app_commands.describe(type="Which log type to disable")
    @app_commands.choices(type=LOG_TYPE_CHOICES)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def disable_log(self, ctx: commands.Context, type: app_commands.Choice[str]):
        assert ctx.guild.id is not None
        if not await self._require_admin(ctx):
            return

        if type.value == "message":
            await db.clear_log_channel(ctx.guild.id)
            description = "Message edit/delete logs have been disabled."
        elif type.value == "say":
            await db.clear_say_log_channel(ctx.guild.id)
            description = "/say moderation logs have been disabled."
        elif type.value == "voice":
            await db.remove_voice_log_channel(ctx.guild.id)
            description = "Voice activity logs have been disabled."
        elif type.value == "moderation":
            await db.clear_mod_log_channel(ctx.guild.id)
            description = "Moderation action logs have been disabled."
        elif type.value == "traffic":
            await db.clear_traffic_log_channel(ctx.guild.id)
            description = "User traffic logs have been disabled."
        elif type.value == "ticket":
            await db.clear_ticket_log_channel(ctx.guild.id)
            description = "Ticket logs have been disabled."
        else:
            await db.disable_level_log_channel(ctx.guild.id)
            description = "Level-up logs are now disabled everywhere."

        embed = discord.Embed(
            title="✅ Log Type Disabled",
            description=description,
            color=await get_guild_color(ctx.guild.id),
        )
        await ctx.send(embed=embed, ephemeral=True)

    @log_group.command(name="status", description="View all current log settings")
    @commands.guild_only()
    async def log_status(self, ctx: commands.Context):
        assert ctx.guild is not None
        assert ctx.guild.id is not None

        message_log_channel_id = await db.get_log_channel_id(ctx.guild.id)
        say_log_channel_id = await db.get_say_log_channel_id(ctx.guild.id)
        voice_log_channel_id = await db.get_voice_log_channel_id(ctx.guild.id)
        level_log_channel_id = await db.get_level_log_channel_id(ctx.guild.id)
        mod_log_channel_id = await db.get_mod_log_channel_id(ctx.guild.id)
        traffic_log_channel_id = await db.get_traffic_log_channel_id(ctx.guild.id)
        ticket_log_channel_id = await db.get_ticket_log_channel_id(ctx.guild.id)

        embed = discord.Embed(
            title="📋 Log Status",
            color=await get_guild_color(ctx.guild.id),
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
        embed.add_field(
            name="Moderation Logs",
            value=(
                f"{await self._channel_display(ctx.guild, mod_log_channel_id)}\n"
                "Covers warn, kick, ban, and timeout actions."
            ),
            inline=False,
        )
        embed.add_field(
            name="User Traffic Logs",
            value=(
                f"{await self._channel_display(ctx.guild, traffic_log_channel_id)}\n"
                "Covers member joins and leaves."
            ),
            inline=False,
        )
        embed.add_field(
            name="Ticket Logs",
            value=(
                f"{await self._channel_display(ctx.guild, ticket_log_channel_id)}\n"
                "Covers closed ticket summaries and transcripts."
            ),
            inline=False,
        )
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LogConfigCog(bot))
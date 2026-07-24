import json

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands

from core import database_pg as db
from cogs.server_management.welcome import WelcomeDashboardView
from utils.embeds import get_embed_color, get_guild_color, process_member_text


LOG_TYPE_CHOICES = [
    app_commands.Choice(name="Message Logs", value="message"),
    app_commands.Choice(name="Say Logs", value="say"),
    app_commands.Choice(name="Voice Logs", value="voice"),
    app_commands.Choice(name="Level Logs", value="level"),
    app_commands.Choice(name="Moderation Logs", value="moderation"),
    app_commands.Choice(name="User Traffic Logs", value="traffic"),
    app_commands.Choice(name="Traffic: Member Joins", value="traffic_join"),
    app_commands.Choice(name="Traffic: Member Leaves", value="traffic_leave"),
    app_commands.Choice(name="Traffic: Server Boosts", value="traffic_boost"),
    app_commands.Choice(name="Ticket Logs", value="ticket"),
]

TRAFFIC_EMBED_CHOICES = [
    app_commands.Choice(name="Member joins", value="join"),
    app_commands.Choice(name="Member leaves", value="leave"),
    app_commands.Choice(name="Server boosts", value="boost"),
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
            await db.enable_traffic_events(ctx.guild.id)
            description = f"All user traffic logs will now use {channel.mention} unless a dedicated channel is configured."
        elif type.value.startswith("traffic_"):
            event = type.value.removeprefix("traffic_")
            await db.set_traffic_event_channel(ctx.guild.id, event, channel.id)
            description = f"Traffic {event} logs will now be sent to {channel.mention}."
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

    def _default_traffic_embed(self, event: str, color: discord.Color) -> discord.Embed:
        if event == "join":
            title = "{user.name} joined the server"
            fields = [
                ("User", "{user}", True),
                ("Account creation", "{account_created}", True),
                ("Member count", "{member_count}", True),
            ]
        elif event == "leave":
            title = "{user.name} left the server"
            fields = [
                ("User", "{user}", True),
                ("Joined date", "{joined_at}", True),
                ("Member count", "{member_count}", True),
            ]
        else:
            title = "{user.name} boosted the server"
            fields = [
                ("User", "{user}", True),
                ("Member count", "{member_count}", True),
            ]

        embed = discord.Embed(
            title=title,
            description="",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url="{user.avatar}")
        embed.set_footer(text="{server} • {member_count} members", icon_url="{server.icon}")
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        return embed

    async def _traffic_embed_from_config(self, guild_id: int, event: str) -> discord.Embed:
        embed = self._default_traffic_embed(
            event,
            await get_embed_color(guild_id, f"traffic_{event}"),
        )
        config = await db.get_traffic_embed_config(guild_id, event)
        if not config:
            return embed

        embed.title = config.get("title")
        embed.description = config.get("description")
        embed.timestamp = discord.utils.utcnow() if config.get("timestamp_enabled", True) else None

        if config.get("author_name"):
            embed.set_author(name=config["author_name"], icon_url=config.get("author_icon"))
        else:
            embed.remove_author()
        if config.get("footer_text"):
            embed.set_footer(text=config["footer_text"], icon_url=config.get("footer_icon"))
        else:
            embed.remove_footer()
        if config.get("thumbnail"):
            embed.set_thumbnail(url=config["thumbnail"])
        else:
            embed.set_thumbnail(url=None)
        if config.get("image"):
            embed.set_image(url=config["image"])
        else:
            embed.set_image(url=None)

        embed.clear_fields()
        fields = config.get("fields") or []
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except (TypeError, json.JSONDecodeError):
                fields = []
        for field in fields[:25]:
            if isinstance(field, dict) and field.get("name") and field.get("value"):
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=bool(field.get("inline", False)),
                )
        return embed

    async def _save_traffic_embed(self, guild_id: int, event: str, embed: discord.Embed):
        payload = embed.to_dict()
        author = payload.get("author") or {}
        footer = payload.get("footer") or {}
        thumbnail = payload.get("thumbnail") or {}
        image = payload.get("image") or {}
        await db.set_traffic_embed_config(
            guild_id,
            event,
            title=payload.get("title"),
            description=payload.get("description"),
            author_name=author.get("name"),
            author_icon=author.get("icon_url"),
            footer_text=footer.get("text"),
            footer_icon=footer.get("icon_url"),
            thumbnail=thumbnail.get("url"),
            image=image.get("url"),
            fields=payload.get("fields", []),
            timestamp_enabled=embed.timestamp is not None,
        )
        if embed.color:
            await db.set_embed_color(guild_id, f"traffic_{event}", embed.color.value)

    def _render_traffic_preview(
        self,
        embed: discord.Embed,
        event: str,
        member: discord.Member,
    ) -> discord.Embed:
        """Render placeholders for the visual editor without changing saved templates."""
        data = embed.to_dict()
        now = embed.timestamp or discord.utils.utcnow()
        extra_values = {
            "account_created": f"<t:{int(member.created_at.timestamp())}:f>",
            "joined_at": (
                f"<t:{int(member.joined_at.timestamp())}:f>"
                if member.joined_at else "Unknown"
            ),
            "event": event,
        }

        def render(value: str | None, *, footer: bool = False) -> str | None:
            if not value:
                return None
            return process_member_text(
                value,
                member,
                event_time=now,
                time_value="" if footer else None,
                extra_values=extra_values,
            ) or None

        fields = list(data.get("fields", []))
        preview = discord.Embed.from_dict(data)
        preview.title = render(data.get("title"))
        preview.description = render(data.get("description"))

        author = data.get("author")
        if author and author.get("name"):
            preview.set_author(
                name=render(author.get("name")) or " ",
                icon_url=render(author.get("icon_url")),
            )
        else:
            preview.remove_author()

        footer = data.get("footer")
        if footer and footer.get("text"):
            preview.set_footer(
                text=render(footer.get("text"), footer=True) or " ",
                icon_url=render(footer.get("icon_url")),
            )
        else:
            preview.remove_footer()

        thumbnail = data.get("thumbnail")
        preview.set_thumbnail(url=render(thumbnail.get("url")) if thumbnail else None)
        image = data.get("image")
        preview.set_image(url=render(image.get("url")) if image else None)

        preview.clear_fields()
        for field in fields[:25]:
            preview.add_field(
                name=render(field.get("name")) or "Field",
                value=(render(field.get("value")) or "-")[:1024],
                inline=bool(field.get("inline", False)),
            )
        return preview

    @log_group.command(name="embed", description="Open the visual editor for a traffic embed")
    @app_commands.choices(event=TRAFFIC_EMBED_CHOICES)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def configure_traffic_embed(self, ctx: commands.Context, event: app_commands.Choice[str]):
        if not await self._require_admin(ctx):
            return
        editor = WelcomeDashboardView(self, ctx, traffic_event=event.value)
        await editor.fetch_state()
        await ctx.send(
            embed=await editor._build_editor_embed(),
            view=editor,
            ephemeral=True,
        )
        content, preview_embed = await editor._build_preview(ctx, preview_mode=True)
        editor.preview_message = await ctx.send(
            content=content or "**Live Preview:**",
            embed=preview_embed,
            ephemeral=True,
        )

    @log_group.command(name="embed-reset", description="Reset one traffic embed to defaults")
    @app_commands.describe(event="Which traffic embed to reset")
    @app_commands.choices(event=TRAFFIC_EMBED_CHOICES)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def reset_traffic_embed(self, ctx: commands.Context, event: app_commands.Choice[str]):
        if not await self._require_admin(ctx):
            return
        await db.reset_traffic_embed_config(ctx.guild.id, event.value)
        await db.reset_embed_color(ctx.guild.id, f"traffic_{event.value}")
        await ctx.send(f"✅ The **{event.name}** embed was reset to defaults.", ephemeral=True)

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
            description = "The shared traffic channel was cleared. Dedicated traffic channels remain active."
        elif type.value.startswith("traffic_"):
            event = type.value.removeprefix("traffic_")
            await db.clear_traffic_event_channel(ctx.guild.id, event)
            description = f"Traffic {event} logs now fall back to the shared traffic channel."
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
            await db.set_traffic_log_channel(ctx.guild.id, 0)
            for event in ("join", "leave", "boost"):
                await db.set_traffic_event_channel(ctx.guild.id, event, 0)
            description = "User traffic logs have been disabled."
        elif type.value.startswith("traffic_"):
            event = type.value.removeprefix("traffic_")
            await db.set_traffic_event_channel(ctx.guild.id, event, 0)
            description = f"Traffic {event} logs are now disabled."
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
        traffic_join_channel_id = await db.get_traffic_event_channel_id(ctx.guild.id, "join")
        traffic_leave_channel_id = await db.get_traffic_event_channel_id(ctx.guild.id, "leave")
        traffic_boost_channel_id = await db.get_traffic_event_channel_id(ctx.guild.id, "boost")
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
                "Shared fallback channel for joins, leaves, and boosts."
            ),
            inline=False,
        )
        embed.add_field(
            name="Traffic: Member Joins",
            value=(
                "Uses shared fallback"
                if traffic_join_channel_id is None
                else await self._channel_display(ctx.guild, traffic_join_channel_id)
            ),
            inline=True,
        )
        embed.add_field(
            name="Traffic: Member Leaves",
            value=(
                "Uses shared fallback"
                if traffic_leave_channel_id is None
                else await self._channel_display(ctx.guild, traffic_leave_channel_id)
            ),
            inline=True,
        )
        embed.add_field(
            name="Traffic: Server Boosts",
            value=(
                "Uses shared fallback"
                if traffic_boost_channel_id is None
                else await self._channel_display(ctx.guild, traffic_boost_channel_id)
            ),
            inline=True,
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
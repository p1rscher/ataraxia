import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class StickyMessageCog(commands.Cog):
    """Keep one bot-authored message reposted at the bottom of a channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._channel_locks: dict[int, asyncio.Lock] = {}

    def _lock_for_channel(self, channel_id: int) -> asyncio.Lock:
        lock = self._channel_locks.get(channel_id)
        if lock is None:
            lock = asyncio.Lock()
            self._channel_locks[channel_id] = lock
        return lock

    async def _resolve_target_message(
        self,
        ctx: commands.Context,
        message_id: Optional[str],
    ) -> Optional[discord.Message]:
        if ctx.message and ctx.message.reference and ctx.message.reference.message_id:
            try:
                return await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.HTTPException:
                pass

        if not message_id:
            return None

        raw_value = message_id.strip()
        if "discord.com/channels/" in raw_value:
            parts = raw_value.split("/")
            try:
                channel_id = int(parts[-2])
                target_message_id = int(parts[-1])
            except (ValueError, IndexError):
                return None

            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await ctx.guild.fetch_channel(channel_id)
                except discord.HTTPException:
                    return None
            if not isinstance(channel, discord.TextChannel):
                return None
            try:
                return await channel.fetch_message(target_message_id)
            except discord.HTTPException:
                return None

        try:
            target_message_id = int(raw_value)
        except ValueError:
            return None

        try:
            return await ctx.channel.fetch_message(target_message_id)
        except discord.HTTPException:
            return None

    async def _clone_attachments(self, source_message: discord.Message) -> list[discord.File]:
        files = []
        for attachment in source_message.attachments:
            try:
                files.append(await attachment.to_file())
            except Exception as exc:
                logger.warning(
                    "Could not clone attachment %s from sticky source %s: %s",
                    getattr(attachment, "id", "unknown"),
                    source_message.id,
                    exc,
                )
        return files

    async def _post_sticky_copy(
        self,
        target_channel: discord.TextChannel,
        source_message: discord.Message,
    ) -> discord.Message:
        files = await self._clone_attachments(source_message)
        embeds = [discord.Embed.from_dict(embed.to_dict()) for embed in source_message.embeds]
        kwargs = {
            "content": source_message.content or None,
            "embeds": embeds,
            "files": files,
            "allowed_mentions": discord.AllowedMentions.none(),
            "silent": True,
        }
        if source_message.stickers:
            kwargs["stickers"] = list(source_message.stickers)

        try:
            return await target_channel.send(**kwargs)
        except TypeError:
            kwargs.pop("stickers", None)
            kwargs.pop("silent", None)
            return await target_channel.send(**kwargs)

    async def _delete_active_sticky(
        self,
        guild: discord.Guild,
        sticky: dict,
    ) -> None:
        active_message_id = sticky.get("active_message_id")
        if not active_message_id:
            return
        if active_message_id == sticky.get("source_message_id"):
            return

        channel = guild.get_channel(sticky["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            try:
                fetched = await guild.fetch_channel(sticky["channel_id"])
                channel = fetched if isinstance(fetched, discord.TextChannel) else None
            except discord.HTTPException:
                channel = None
        if channel is None:
            return

        try:
            message = await channel.fetch_message(active_message_id)
            await message.delete()
        except discord.NotFound:
            pass
        except discord.HTTPException as exc:
            logger.warning(
                "Failed to delete active sticky message %s in channel %s: %s",
                active_message_id,
                sticky["channel_id"],
                exc,
            )

    async def _refresh_sticky_message(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> Optional[discord.Message]:
        sticky = await db.get_sticky_message(guild.id, channel_id)
        if not sticky:
            return None

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                fetched = await guild.fetch_channel(channel_id)
                channel = fetched if isinstance(fetched, discord.TextChannel) else None
            except discord.HTTPException:
                channel = None
        if not isinstance(channel, discord.TextChannel):
            return None

        source_channel = guild.get_channel(sticky["source_channel_id"])
        if source_channel is None:
            try:
                fetched = await guild.fetch_channel(sticky["source_channel_id"])
                source_channel = fetched if isinstance(fetched, discord.TextChannel) else None
            except discord.HTTPException:
                source_channel = None
        if not isinstance(source_channel, discord.TextChannel):
            return None

        try:
            source_message = await source_channel.fetch_message(sticky["source_message_id"])
        except discord.HTTPException as exc:
            logger.warning(
                "Could not fetch sticky source message %s in channel %s: %s",
                sticky["source_message_id"],
                sticky["source_channel_id"],
                exc,
            )
            return None

        await self._delete_active_sticky(guild, sticky)
        posted_message = await self._post_sticky_copy(channel, source_message)
        await db.update_sticky_message_active_id(guild.id, channel_id, posted_message.id)
        return posted_message

    @commands.hybrid_group(
        name="stickymessage",
        description="Keep a bot message reposted at the bottom of a channel",
    )
    @commands.guild_only()
    async def sticky_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "ℹ️ Use `/stickymessage set`, `/stickymessage clear`, `/stickymessage status`, or `/stickymessage refresh`.",
                ephemeral=True,
            )

    @sticky_group.command(name="set", description="Use a bot-authored message as the sticky bottom message for a channel")
    @app_commands.describe(
        message_id="Message ID or Discord link; optional if you reply to the bot message",
        channel="The channel that should keep the sticky message at the bottom",
    )
    @commands.has_permissions(administrator=True)
    async def sticky_set(
        self,
        ctx: commands.Context,
        message_id: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
    ):
        assert ctx.guild is not None

        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("❌ This command can only target a text channel.", ephemeral=True)
            return

        if not target_channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(
                f"❌ I cannot send messages in {target_channel.mention}.",
                ephemeral=True,
            )
            return

        source_message = await self._resolve_target_message(ctx, message_id)
        if source_message is None:
            await ctx.send(
                "❌ Reply to a bot message or provide a valid message ID/link.",
                ephemeral=True,
            )
            return

        if source_message.guild is None or source_message.guild.id != ctx.guild.id:
            await ctx.send("❌ The source message must be from this server.", ephemeral=True)
            return

        if not source_message.author.bot:
            await ctx.send("❌ Only bot-authored messages can be used as sticky messages.", ephemeral=True)
            return

        lock = self._lock_for_channel(target_channel.id)
        async with lock:
            old_sticky = await db.get_sticky_message(ctx.guild.id, target_channel.id)
            if old_sticky:
                await self._delete_active_sticky(ctx.guild, old_sticky)

            await db.set_sticky_message(
                ctx.guild.id,
                target_channel.id,
                source_message.channel.id,
                source_message.id,
                active_message_id=None,
                created_by=ctx.author.id,
            )
            posted = await self._refresh_sticky_message(ctx.guild, target_channel.id)

        if posted is None:
            await ctx.send(
                "❌ The sticky configuration was saved, but I could not repost the selected message.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="✅ Sticky Message Enabled",
            description=(
                f"I will keep a copy of the selected bot message at the bottom of {target_channel.mention}.\n\n"
                f"Source: [Jump to message]({source_message.jump_url})"
            ),
            color=await get_guild_color(ctx.guild.id),
        )
        embed.add_field(name="Current sticky message", value=f"[Jump]({posted.jump_url})", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @sticky_group.command(name="clear", description="Disable the sticky bottom message for a channel")
    @app_commands.describe(channel="The target channel; defaults to the current channel")
    @commands.has_permissions(administrator=True)
    async def sticky_clear(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ):
        assert ctx.guild is not None

        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("❌ This command can only target a text channel.", ephemeral=True)
            return

        lock = self._lock_for_channel(target_channel.id)
        async with lock:
            sticky = await db.get_sticky_message(ctx.guild.id, target_channel.id)
            if not sticky:
                await ctx.send("ℹ️ No sticky message is configured for that channel.", ephemeral=True)
                return
            await self._delete_active_sticky(ctx.guild, sticky)
            await db.clear_sticky_message(ctx.guild.id, target_channel.id)

        await ctx.send(
            f"✅ Sticky bottom message disabled for {target_channel.mention}.",
            ephemeral=True,
        )

    @sticky_group.command(name="refresh", description="Repost the sticky message immediately")
    @app_commands.describe(channel="The target channel; defaults to the current channel")
    @commands.has_permissions(administrator=True)
    async def sticky_refresh(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ):
        assert ctx.guild is not None

        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("❌ This command can only target a text channel.", ephemeral=True)
            return

        lock = self._lock_for_channel(target_channel.id)
        async with lock:
            posted = await self._refresh_sticky_message(ctx.guild, target_channel.id)

        if posted is None:
            await ctx.send(
                "❌ No sticky message could be reposted for that channel.",
                ephemeral=True,
            )
            return

        await ctx.send(
            f"✅ Sticky message reposted in {target_channel.mention}: [Jump]({posted.jump_url})",
            ephemeral=True,
        )

    @sticky_group.command(name="status", description="Show the configured sticky bottom message for a channel")
    @app_commands.describe(channel="The target channel; defaults to the current channel")
    async def sticky_status(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
    ):
        assert ctx.guild is not None

        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("❌ This command can only target a text channel.", ephemeral=True)
            return

        sticky = await db.get_sticky_message(ctx.guild.id, target_channel.id)
        if not sticky:
            await ctx.send(
                f"ℹ️ No sticky message is configured for {target_channel.mention}.",
                ephemeral=True,
            )
            return

        source_channel = ctx.guild.get_channel(sticky["source_channel_id"])
        source_ref = (
            f"<#{sticky['source_channel_id']}> / `{sticky['source_message_id']}`"
            if source_channel is None
            else f"{source_channel.mention} / `{sticky['source_message_id']}`"
        )
        current_ref = (
            f"`{sticky['active_message_id']}`" if sticky.get("active_message_id") else "Not currently posted"
        )
        embed = discord.Embed(
            title="📌 Sticky Message Status",
            color=await get_guild_color(ctx.guild.id),
        )
        embed.add_field(name="Target Channel", value=target_channel.mention, inline=False)
        embed.add_field(name="Source Message", value=source_ref, inline=False)
        embed.add_field(name="Current Live Copy", value=current_ref, inline=False)
        embed.set_footer(text="The sticky copy is deleted and reposted whenever a user sends a new message.")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        sticky = await db.get_sticky_message(message.guild.id, message.channel.id)
        if not sticky:
            return

        lock = self._lock_for_channel(message.channel.id)
        async with lock:
            try:
                await self._refresh_sticky_message(message.guild, message.channel.id)
            except discord.HTTPException as exc:
                logger.warning(
                    "Failed to refresh sticky message in guild %s channel %s: %s",
                    message.guild.id,
                    message.channel.id,
                    exc,
                )
            except Exception:
                logger.exception(
                    "Unexpected error while refreshing sticky message in guild %s channel %s",
                    message.guild.id,
                    message.channel.id,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessageCog(bot))
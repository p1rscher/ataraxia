from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PendingMessage:
    message_id: int
    guild_id: int
    channel_id: int
    author_id: int
    content: str
    created_at: object = None
    edited_at: object = None
    version: int = 1

    def as_bulk_record(self) -> dict:
        return {
            "message_id": self.message_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "author_id": self.author_id,
            "content": self.content,
            "created_at": self.created_at,
            "edited_at": self.edited_at,
        }

    def as_message_row(self):
        return (
            self.message_id,
            self.guild_id,
            self.channel_id,
            self.author_id,
            self.content,
            self.created_at,
            self.edited_at,
            None,
            1,
        )


class MessageCacheManager:
    def __init__(self, bot, flush_interval: float = 10.0):
        self.bot = bot
        self.flush_interval = flush_interval
        self._messages: dict[int, PendingMessage] = {}
        self._state_lock = asyncio.Lock()
        self._flush_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    async def start(self):
        self._flush_task = asyncio.create_task(self._periodic_flush(), name="message-cache-flush")

    async def close(self):
        if self._closed:
            return
        self._closed = True

        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self.flush_pending()

    async def queue_message(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        author_id: int,
        content: str,
        created_at=None,
        edited_at=None,
    ):
        async with self._state_lock:
            pending = self._messages.get(message_id)
            if pending is None:
                self._messages[message_id] = PendingMessage(
                    message_id=message_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    author_id=author_id,
                    content=content,
                    created_at=created_at,
                    edited_at=edited_at,
                )
                return

            pending.guild_id = guild_id
            pending.channel_id = channel_id
            pending.author_id = author_id
            pending.content = content
            pending.created_at = pending.created_at or created_at
            pending.edited_at = edited_at or pending.edited_at
            pending.version += 1

    async def update_message(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        author_id: int,
        content: str,
        created_at=None,
        edited_at=None,
        force_update: bool = False,
    ):
        async with self._state_lock:
            pending = self._messages.get(message_id)
            if pending is not None:
                pending.guild_id = guild_id
                pending.channel_id = channel_id
                pending.author_id = author_id
                pending.content = content
                pending.created_at = pending.created_at or created_at
                pending.edited_at = edited_at or pending.edited_at
                pending.version += 1
                return

        await self.bot.db.save_message(
            message_id=message_id,
            guild_id=guild_id,
            channel_id=channel_id,
            author_id=author_id,
            content=content,
            created_at=created_at,
            edited_at=edited_at,
            force_update=force_update,
        )

    async def get_message(self, message_id: int):
        async with self._state_lock:
            pending = self._messages.get(message_id)
            if pending is not None:
                return pending.as_message_row()

        return await self.bot.db.get_message(message_id)

    async def mark_deleted(self, message_id: int):
        async with self._flush_lock:
            pending = None
            async with self._state_lock:
                current = self._messages.get(message_id)
                if current is not None:
                    pending = replace(current)

            if pending is not None:
                await self.bot.db.bulk_save_messages([pending.as_bulk_record()])
                async with self._state_lock:
                    current = self._messages.get(message_id)
                    if current is not None and current.version == pending.version:
                        self._messages.pop(message_id, None)

            await self.bot.db.mark_message_deleted(message_id)

    async def flush_pending(self, message_id: Optional[int] = None):
        async with self._flush_lock:
            async with self._state_lock:
                if message_id is None:
                    snapshot = {mid: replace(message) for mid, message in self._messages.items()}
                else:
                    pending = self._messages.get(message_id)
                    snapshot = {message_id: replace(pending)} if pending is not None else {}

            if not snapshot:
                return

            try:
                await self.bot.db.bulk_save_messages(
                    [message.as_bulk_record() for message in snapshot.values()]
                )
            except Exception:
                logger.exception("Failed to flush pending messages")
                return

            async with self._state_lock:
                for mid, snapshot_message in snapshot.items():
                    current = self._messages.get(mid)
                    if current is not None and current.version == snapshot_message.version:
                        self._messages.pop(mid, None)

    async def _periodic_flush(self):
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in message cache flush loop")
# utils/stream_responder.py
"""
Edits a single Discord message in place while text streams in from the AI
backend, without exceeding Discord's edit rate limit.

Design
------
A background task wakes up every ``min_interval`` seconds and, if the text
has changed since the last edit, pushes exactly one ``message.edit(...)``.
The producer (the loop reading from ``ai_client.stream_chat``) only ever
updates an in-memory string via ``update()`` - it never talks to Discord
directly. This guarantees at most one edit per interval *regardless of how
often or irregularly new tokens arrive*, which is the actual constraint
Discord enforces (a handful of edits per few seconds on the same message
route), rather than trying to time individual token arrivals.

A fast response that finishes inside the first interval results in exactly
one edit (the final one) - the same as today's non-streaming code path. A
slow response gets progressive updates every ~2s. No separate "is this
answer long enough to stream" branch is needed; the throttle makes that
distinction on its own.

Usage
-----
    async with StreamingResponder(message, render=my_render_fn) as responder:
        async for delta in client.stream_chat(...):
            full_text += delta
            responder.update(full_text)
    # __aexit__ guarantees one last edit with the final text.

``render(text, *, done, error)`` must return a dict of keyword arguments
for ``discord.Message.edit`` (e.g. ``{"embed": ...}`` or ``{"content": ...}``).
It is called with ``done=False`` for in-progress edits and once more with
``done=True`` (and ``error`` set if the stream raised) for the final edit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

import discord

logger = logging.getLogger(__name__)

RenderFn = Callable[[str, bool, Optional[BaseException]], dict]


class StreamingResponder:
    def __init__(
        self,
        message: discord.Message,
        render: RenderFn,
        min_interval: float = 2.0,
    ) -> None:
        self._message = message
        self._render = render
        self._min_interval = min_interval

        self._latest_text = ""
        self._last_sent_text: Optional[str] = None
        self._done = False
        self._task: Optional[asyncio.Task] = None

    def update(self, text: str) -> None:
        """Record the current full text. Cheap - does not touch Discord."""
        self._latest_text = text

    async def __aenter__(self) -> "StreamingResponder":
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._done = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Guaranteed final edit, even if it lands inside the throttle
        # window - the user should never be left looking at a stale
        # "still typing" state.
        await self._push(done=True, error=exc)
        # Don't suppress the original exception, if any.
        return False

    async def _loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._min_interval)
                await self._push(done=False, error=None)
        except asyncio.CancelledError:
            raise

    async def _push(self, *, done: bool, error: Optional[BaseException]) -> None:
        text = self._latest_text
        if not done and text == self._last_sent_text:
            return  # nothing new since the last edit, skip the API call
        if done and text == self._last_sent_text and error is None:
            return  # last progress edit already showed the final text

        kwargs = self._render(text, done, error)
        try:
            await self._message.edit(**kwargs)
            self._last_sent_text = text
        except discord.HTTPException as exc:
            status = getattr(exc, "status", None)
            if status == 429:
                retry_after = getattr(exc, "retry_after", None) or self._min_interval
                logger.warning(
                    "stream_responder: rate limited on message %s, backing off %.1fs",
                    self._message.id, retry_after,
                )
                # Don't raise: a skipped edit just means the user sees the
                # previous snapshot a bit longer. The next tick (or the
                # guaranteed final push) will catch up.
                await asyncio.sleep(retry_after)
            else:
                logger.warning(
                    "stream_responder: edit failed for message %s: %s",
                    self._message.id, exc,
                )

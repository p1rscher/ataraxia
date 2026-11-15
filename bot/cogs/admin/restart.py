"""Restart the bot without cutting off people who are in the middle of a setup.

A full restart throws away every open dialog (embed builder, reaction role
editor, setup wizard, running games, ...). This cog watches button, menu and
modal activity. ``restart`` then stops accepting new commands, waits until
nobody has used a dialog for a while and only then shuts the bot down; the
process manager (systemd, ``Restart=always``) starts it again.

Owner commands (prefix only, hidden):

    restart            wait for open dialogs, then restart
    restart <minutes>  same, but wait at most that long
    restart now        restart immediately
    restart status     show who is currently in a dialog
    restart cancel     abort a pending restart

From a shell on the server, ``systemctl kill -s SIGUSR1 ataraxia-bot`` starts
the same waiting restart. ``systemctl restart`` remains an immediate restart.

Settings (.env): RESTART_IDLE_SECONDS (default 300) is how long after the last
click a dialog still counts as in use; RESTART_MAX_WAIT_SECONDS (default 600)
is the longest a restart waits.
"""

import asyncio
import logging
import os
import re
import signal
import time
from typing import Optional

import discord
from discord.ext import commands

from utils.close import graceful_shutdown

logger = logging.getLogger(__name__)

# discord.py gives the buttons, menus and modals of temporary dialogs a random
# 32-character hex ID. Permanent panels (reaction roles, tickets, temp voice)
# carry fixed IDs and survive a restart, so they do not need to be waited for.
_TEMPORARY_ID_RE = re.compile(r"[0-9a-f]{32}")

PENDING_MESSAGE = (
    "The bot is about to restart for an update and is not taking new commands right now. "
    "Please try again in a few minutes."
)


def _seconds_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int((os.getenv(name, "") or "").strip() or default)
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def is_temporary_dialog(interaction: discord.Interaction) -> bool:
    """True for a click or submit on a dialog that a restart would destroy."""
    if interaction.type not in (
        discord.InteractionType.component,
        discord.InteractionType.modal_submit,
    ):
        return False
    custom_id = (interaction.data or {}).get("custom_id", "")
    return bool(_TEMPORARY_ID_RE.fullmatch(custom_id))


class RestartCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.idle_seconds = _seconds_env("RESTART_IDLE_SECONDS", 300, 10, 3600)
        self.max_wait_seconds = _seconds_env("RESTART_MAX_WAIT_SECONDS", 600, 0, 7200)
        # user id -> (time of last dialog activity, guild id)
        self._activity: dict[int, tuple[float, Optional[int]]] = {}
        self._pending: Optional[asyncio.Task] = None
        self._signal_installed = False

    # ------------------------------------------------------------ lifecycle

    async def cog_load(self):
        self.bot.add_check(self._block_while_pending)
        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, self._on_signal)
            self._signal_installed = True
        except (NotImplementedError, AttributeError, ValueError):
            pass  # not available on this platform

    async def cog_unload(self):
        self.bot.remove_check(self._block_while_pending)
        if self._signal_installed:
            try:
                asyncio.get_running_loop().remove_signal_handler(signal.SIGUSR1)
            except Exception:
                pass
        if self._pending and not self._pending.done():
            self._pending.cancel()

    # -------------------------------------------------------------- tracking

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if is_temporary_dialog(interaction) and interaction.user is not None:
            self._activity[interaction.user.id] = (time.monotonic(), interaction.guild_id)

    def active_sessions(self) -> dict[int, tuple[float, Optional[int]]]:
        """Users who used a temporary dialog within the idle window."""
        cutoff = time.monotonic() - self.idle_seconds
        self._activity = {uid: entry for uid, entry in self._activity.items() if entry[0] > cutoff}
        return dict(self._activity)

    @property
    def pending(self) -> bool:
        return self._pending is not None and not self._pending.done()

    async def _block_while_pending(self, ctx: commands.Context) -> bool:
        if not self.pending or await self.bot.is_owner(ctx.author):
            return True
        raise commands.CheckFailure(PENDING_MESSAGE)

    def describe_sessions(self) -> str:
        sessions = self.active_sessions()
        if not sessions:
            return "Nobody is in a dialog right now."
        now = time.monotonic()
        lines = []
        for user_id, (last, guild_id) in sorted(sessions.items(), key=lambda item: -item[1][0]):
            guild = self.bot.get_guild(guild_id) if guild_id else None
            where = guild.name if guild else "direct message"
            lines.append(f"• <@{user_id}> in **{where}**, last click {int(now - last)}s ago")
        return "\n".join(lines[:15])

    # --------------------------------------------------------------- restart

    async def wait_for_idle(self, max_wait: float, poll: float = 5.0) -> bool:
        """Wait until no dialog is in use. Returns False if ``max_wait`` ran out first."""
        deadline = time.monotonic() + max_wait
        while self.active_sessions():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(poll, remaining))
        return True

    async def _drain_and_restart(self, max_wait: float, notify=None):
        async def say(text: str):
            logger.info("restart: %s", text.replace("\n", " | "))
            if notify is not None:
                try:
                    await notify(text)
                except Exception:
                    pass

        try:
            waiting = len(self.active_sessions())
            if waiting:
                await say(
                    f"⏳ Waiting for {waiting} open dialog(s), at most {int(max_wait // 60)} min "
                    f"{int(max_wait % 60)} s. New commands are paused.\n{self.describe_sessions()}\n"
                    "`restart now` skips the wait, `restart cancel` aborts."
                )
            if await self.wait_for_idle(max_wait):
                await say("🔄 No open dialogs. Restarting now.")
            else:
                await say(f"🔄 Waited the maximum time. Restarting now; still open:\n{self.describe_sessions()}")
        except asyncio.CancelledError:
            logger.info("restart: cancelled")
            raise
        await asyncio.sleep(0.5)  # let the message go out
        await graceful_shutdown(self.bot)

    def start_restart(self, max_wait: Optional[float] = None, notify=None) -> bool:
        """Begin a waiting restart. Returns False if one is already pending."""
        if self.pending:
            return False
        wait = self.max_wait_seconds if max_wait is None else max_wait
        self._pending = asyncio.create_task(self._drain_and_restart(wait, notify), name="waiting-restart")
        return True

    def _on_signal(self):
        logger.info("restart: requested by SIGUSR1")
        self.start_restart()

    @commands.command(name="restart", hidden=True)
    async def restart(self, ctx: commands.Context, option: Optional[str] = None):
        """Restart once nobody is in the middle of a dialog (owner only)."""
        if not await self.bot.is_owner(ctx.author):
            return
        option = (option or "").strip().lower()

        if option == "status":
            state = "A restart is pending.\n" if self.pending else ""
            await ctx.send(f"{state}{self.describe_sessions()}", allowed_mentions=discord.AllowedMentions.none())
            return

        if option == "cancel":
            if self.pending:
                self._pending.cancel()
                await ctx.send("Restart cancelled. Commands are accepted again.")
            else:
                await ctx.send("No restart is pending.")
            return

        max_wait: Optional[float] = None
        if option == "now":
            max_wait = 0
            if self.pending:
                self._pending.cancel()
        elif option:
            try:
                max_wait = max(0.0, min(float(option), 120.0)) * 60
            except ValueError:
                await ctx.send("Usage: `restart`, `restart <minutes>`, `restart now`, `restart status`, `restart cancel`")
                return

        async def notify(text: str):
            await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())

        logger.info("restart: requested by %s (option=%r)", ctx.author, option)
        if not self.start_restart(max_wait, notify):
            await ctx.send("A restart is already pending. Use `restart now` or `restart cancel`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(RestartCog(bot))

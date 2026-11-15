import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest
from discord.ext import commands

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot"))

from cogs.admin import restart as restart_module  # noqa: E402
from cogs.admin.restart import RestartCog, is_temporary_dialog  # noqa: E402

OWNER, USER = 1, 2


def interaction(kind, custom_id, user_id=USER):
    return SimpleNamespace(type=kind, data={"custom_id": custom_id},
                           user=SimpleNamespace(id=user_id), guild_id=10)


class FakeBot:
    def __init__(self):
        self.checks = []
    def add_check(self, check):
        self.checks.append(check)
    def remove_check(self, check):
        self.checks.remove(check)
    def get_guild(self, guild_id):
        return SimpleNamespace(name="Guild")
    async def is_owner(self, user):
        return user.id == OWNER


def test_ids_generated_by_discord_py_are_recognised_as_temporary():
    """If a discord.py update changes how automatic IDs look, this fails
    instead of restarts silently no longer waiting."""
    async def run():
        class Modal(discord.ui.Modal, title="t"):
            pass
        button = discord.ui.Button(label="x")
        select = discord.ui.Select(options=[discord.SelectOption(label="a")])
        component, submit = discord.InteractionType.component, discord.InteractionType.modal_submit
        assert is_temporary_dialog(interaction(component, button.custom_id))
        assert is_temporary_dialog(interaction(component, select.custom_id))
        assert is_temporary_dialog(interaction(submit, Modal().custom_id))
        # permanent panels and plain commands do not count
        assert not is_temporary_dialog(interaction(component, "rrbtn_123_456"))
        assert not is_temporary_dialog(interaction(component, "rrsel_123"))
        assert not is_temporary_dialog(interaction(discord.InteractionType.application_command, button.custom_id))
    asyncio.run(run())


def test_waits_for_dialogs_and_blocks_new_commands(monkeypatch):
    async def run():
        shutdowns, messages = [], []

        async def fake_shutdown(bot):
            shutdowns.append(time.monotonic())
        monkeypatch.setattr(restart_module, "graceful_shutdown", fake_shutdown)

        async def notify(text):
            messages.append(text)

        bot = FakeBot()
        cog = RestartCog(bot)
        cog.idle_seconds = 0.6
        await cog.cog_load()
        check = bot.checks[0]
        user_ctx = SimpleNamespace(author=SimpleNamespace(id=USER))
        owner_ctx = SimpleNamespace(author=SimpleNamespace(id=OWNER))

        assert await check(user_ctx) is True                    # nothing pending: commands work

        await cog.on_interaction(interaction(discord.InteractionType.component, "a" * 32))
        await cog.on_interaction(interaction(discord.InteractionType.component, "rrbtn_1_2", user_id=99))
        assert list(cog.active_sessions()) == [USER]            # the permanent panel is ignored

        started = time.monotonic()
        assert cog.start_restart(max_wait=30, notify=notify) is True
        assert cog.start_restart(max_wait=30) is False           # only one at a time
        await asyncio.sleep(0.2)
        assert not shutdowns and "Waiting for 1 open dialog" in messages[0]
        with pytest.raises(commands.CheckFailure):
            await check(user_ctx)                                # new commands are paused
        assert await check(owner_ctx) is True                    # the owner still gets through

        # the user keeps clicking: the restart keeps waiting
        await cog.on_interaction(interaction(discord.InteractionType.modal_submit, "b" * 32))
        await asyncio.sleep(0.4)
        assert not shutdowns

        await asyncio.wait_for(cog._pending, timeout=5)
        assert len(shutdowns) == 1 and shutdowns[0] - started >= 0.75   # 0.2s + 0.6s idle
        assert "No open dialogs" in messages[-1]
        await cog.cog_unload()
        assert bot.checks == []
    asyncio.run(run())


def test_gives_up_after_max_wait_and_can_be_cancelled(monkeypatch):
    async def run():
        shutdowns = []

        async def fake_shutdown(bot):
            shutdowns.append(1)
        monkeypatch.setattr(restart_module, "graceful_shutdown", fake_shutdown)

        cog = RestartCog(FakeBot())
        cog.idle_seconds = 60
        await cog.on_interaction(interaction(discord.InteractionType.component, "c" * 32))

        cog.start_restart(max_wait=60)
        await asyncio.sleep(0.1)
        cog._pending.cancel()
        await asyncio.sleep(0.1)
        assert not shutdowns and not cog.pending                 # cancelled: no restart, commands resume
        assert await cog._block_while_pending(SimpleNamespace(author=SimpleNamespace(id=USER))) is True

        cog.start_restart(max_wait=0.3)                          # dialog still open, but time runs out
        await asyncio.wait_for(cog._pending, timeout=5)
        assert shutdowns == [1]

        shutdowns.clear()
        idle = RestartCog(FakeBot())
        idle.start_restart(max_wait=60)                          # nobody active: immediate
        await asyncio.wait_for(idle._pending, timeout=2)
        assert shutdowns == [1]
    asyncio.run(run())

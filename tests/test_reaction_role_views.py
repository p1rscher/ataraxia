"""Builds the real reaction-role views and checks the payload sent to Discord."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot"))

from cogs.server_management import reaction_roles as rr  # noqa: E402

PANEL = {"message_id": 42, "component_type": "Buttons", "role_removal": True, "multiple_slots": True}
ENTRIES = [  # exactly what the screenshot's panel had stored
    {"emoji": "<🩷>", "role_id": 1, "label": None, "description": None},
    {"emoji": "<💚>", "role_id": 2, "label": None, "description": None},
    {"emoji": "<🩵>", "role_id": 3, "label": "he/him", "description": None},
    {"emoji": "<:peepo:123456789012345678>", "role_id": 4, "label": None, "description": None},
]
GUILD = SimpleNamespace(get_role=lambda rid: SimpleNamespace(name=f"role{rid}", members=[]))


def components(view):
    return [c for row in view.to_components() for c in row["components"]]


def test_buttons_send_valid_emoji_names():
    async def run():
        comps = components(rr.DynamicRoleView(PANEL, ENTRIES, GUILD))
        assert [c["emoji"]["name"] for c in comps] == ["🩷", "💚", "🩵", "peepo"]
        assert str(comps[3]["emoji"]["id"]) == "123456789012345678"
        assert comps[2]["label"] == "he/him"
    asyncio.run(run())


def test_select_uses_emoji_field():
    async def run():
        view = rr.DynamicRoleView({**PANEL, "component_type": "Select"}, ENTRIES, GUILD)
        options = components(view)[0]["options"]
        assert options[0]["emoji"]["name"] == "🩷" and options[0]["label"] == "role1"
        assert str(options[3]["emoji"]["id"]) == "123456789012345678"
    asyncio.run(run())


def test_fallback_moves_emoji_into_label():
    async def run():
        comps = components(rr.DynamicRoleView(PANEL, ENTRIES, GUILD, emoji_in_label=True))
        assert all("emoji" not in c or c["emoji"] is None for c in comps)
        assert comps[0]["label"] == "🩷" and comps[2]["label"] == "🩵 he/him"
    asyncio.run(run())


def test_send_role_view_retries_only_on_emoji_rejection():
    class Rejected(discord.HTTPException):
        def __init__(self, code, text):
            self.code, self.text, self.status = code, text, 400
        def __str__(self):
            return self.text

    async def run():
        calls = []

        async def action(view):
            calls.append(view)
            if len(calls) == 1:
                raise Rejected(50035, "In components.0.components.0.emoji.name: Invalid emoji")
            return "sent"

        assert await rr.send_role_view(action, PANEL, ENTRIES, GUILD) == "sent"
        assert len(calls) == 2 and components(calls[1])[0]["label"] == "🩷"

        async def other_error(view):
            raise Rejected(50013, "Missing Permissions")

        with pytest.raises(discord.HTTPException):
            await rr.send_role_view(other_error, PANEL, ENTRIES, GUILD)
    asyncio.run(run())


def test_legacy_values_from_production():
    guild = SimpleNamespace(
        get_role=lambda rid: SimpleNamespace(name=f"role{rid}", members=[]),
        emojis=[SimpleNamespace(name="ghrt", id=555555555555555555, animated=False)],
    )
    entries = [
        {"emoji": ":flag_de:", "role_id": 1, "label": "Deutsch", "description": None},
        {"emoji": ":ghrt:", "role_id": 2, "label": None, "description": None},      # custom emoji saved by name
        {"emoji": "Announcement", "role_id": 3, "label": None, "description": None},  # no emoji at all
        {"emoji": ":gone:", "role_id": 4, "label": None, "description": None},      # custom emoji that was deleted
    ]

    async def run():
        comps = components(rr.DynamicRoleView(PANEL, entries, guild))
        assert comps[0]["emoji"]["name"] == "🇩🇪" and comps[0]["label"] == "Deutsch"
        assert str(comps[1]["emoji"]["id"]) == "555555555555555555"
        assert not comps[2].get("emoji") and comps[2]["label"] == "Announcement"
        assert not comps[3].get("emoji") and comps[3]["label"] == "gone"
        # and the same entries as a select menu
        options = components(rr.DynamicRoleView({**PANEL, "component_type": "Select"}, entries, guild))[0]["options"]
        assert options[0]["emoji"]["name"] == "🇩🇪" and not options[2].get("emoji")
    asyncio.run(run())

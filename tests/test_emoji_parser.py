"""Run with: .venv/bin/python -m pytest tests/test_emoji_parser.py"""
import sys
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot"))

from utils.emoji_parser import emoji_as_text, parse_emoji, to_component_emoji  # noqa: E402

HEART = "❤️"


def fake_emoji(name, eid, animated=False):
    return SimpleNamespace(name=name, id=eid, animated=animated)


GUILD = SimpleNamespace(emojis=[fake_emoji("peepoHappy", 111111111111111111), fake_emoji("heart", 222222222222222222)])
CLIENT = SimpleNamespace(
    emojis=GUILD.emojis + [fake_emoji("dance", 333333333333333333, True)],
    get_emoji=lambda i: next((e for e in CLIENT.emojis if e.id == i), None),
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("🩷", "🩷"),
        ("<🩷>", "🩷"),                      # the case from the bug report
        ("<💚>", "💚"),
        ("<🖤>", "🖤"),
        ("  🩷 she/her ", "🩷"),
        ("❤", HEART),                   # missing variation selector
        (HEART, HEART),
        (f"<{HEART}>", HEART),
        ("​😀​", "😀"),
        (":smile:", "😄"),
        (":red_heart:", HEART),
        (":tools:", "🛠️"),
        (":gear:", "⚙️"),
        ("🇩🇪", "🇩🇪"),
        ("1️⃣", "1️⃣"),
        ("👍🏽", "👍🏽"),
        ("👨‍👩‍👧", "👨‍👩‍👧"),
        ("<:peepoHappy:123456789012345678>", "<:peepoHappy:123456789012345678>"),
        ("<a:dance:123456789012345678>", "<a:dance:123456789012345678>"),
        (" <:peepoHappy:123456789012345678> role", "<:peepoHappy:123456789012345678>"),
        (":peepoHappy:123456789012345678", "<:peepoHappy:123456789012345678>"),
        ("a:dance:123456789012345678", "<a:dance:123456789012345678>"),
        ("123456789012345678", "<:emoji:123456789012345678>"),
        # values found in the production database
        ("<:pink_heart:>", "🩷"),
        ("<:green_heart:>", "💚"),
        (":flag_de:", "🇩🇪"),
        (":flag_us:", "🇺🇸"),
        (":loudspeaker:", "📢"),
        (":bulb:", "💡"),
        ("\u26a7", "\u26a7\ufe0f"),
        ("👤👤", "👤"),
        (":thumbsup_tone3:", "👍🏽"),
        (":wave_tone1:", "👋🏻"),
        ("Announcement", None),
        (":flag_zz:", None),
        ("", None),
        ("   ", None),
        ("hello", None),
        (":definitely_not_an_emoji:", None),
        ("<>", None),
        (None, None),
    ],
)
def test_parse_without_context(raw, expected):
    assert parse_emoji(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (":peepoHappy:", "<:peepoHappy:111111111111111111>"),
        ("peepoHappy", "<:peepoHappy:111111111111111111>"),
        (":peepohappy:", "<:peepoHappy:111111111111111111>"),
        (":heart:", "<:heart:222222222222222222>"),     # this server's emoji wins
        (":dance:", "<a:dance:333333333333333333>"),   # other server, animated
        ("333333333333333333", "<a:dance:333333333333333333>"),
        (":smile:", "😄"),
        (":peepoHappy~1:", "<:peepoHappy:111111111111111111>"),   # Discord's duplicate-name suffix
    ],
)
def test_parse_with_guild(raw, expected):
    assert parse_emoji(raw, GUILD, CLIENT) == expected


def test_heart_shortcode_without_guild():
    assert parse_emoji(":heart:") == HEART


def test_component_emoji_repairs_legacy_values():
    assert to_component_emoji("<🩷>") == "🩷"
    assert to_component_emoji(":smile:") == "😄"
    custom = to_component_emoji("<a:dance:123456789012345678>")
    assert isinstance(custom, discord.PartialEmoji)
    assert (custom.name, custom.id, custom.animated) == ("dance", 123456789012345678, True)
    assert to_component_emoji("nonsense") is None
    assert to_component_emoji(None) is None


def test_component_payload_is_what_discord_expects():
    button = discord.ui.Button(label="x", emoji=to_component_emoji("<🩷>"), custom_id="a")
    payload = button.to_component_dict()["emoji"]
    assert payload["name"] == "🩷" and not payload.get("id")
    button = discord.ui.Button(label="x", emoji=to_component_emoji("<:peepoHappy:123456789012345678>"), custom_id="b")
    payload = button.to_component_dict()["emoji"]
    assert payload["name"] == "peepoHappy" and str(payload["id"]) == "123456789012345678"


def test_emoji_as_text_keeps_unknown_values():
    assert emoji_as_text("<🩷>") == "🩷"
    assert emoji_as_text("weird") == "weird"

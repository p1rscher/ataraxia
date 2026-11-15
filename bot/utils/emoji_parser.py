"""Turn whatever a user types into an emoji Discord accepts.

Text inputs (modals, command arguments) deliver emojis in many shapes:

* the Unicode character itself, with or without a variation selector
* a shortcode such as ``:heart:``
* a custom emoji tag ``<:name:id>`` / ``<a:name:id>``
* a custom emoji *name* (``:peepoHappy:`` or ``peepoHappy``), because Discord
  does not expand custom emojis inside modal text fields
* a bare custom emoji ID
* any of the above wrapped in stray characters, e.g. ``<🩷>`` or ``🩷 she/her``

``parse_emoji`` reduces all of these to one canonical string that is safe to
store: the Unicode emoji itself, or ``<:name:id>`` / ``<a:name:id>``.
``to_component_emoji`` converts a stored value into what discord.py expects for
buttons and select options.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Union

import discord
import emoji as emoji_lib

__all__ = [
    "parse_emoji",
    "to_component_emoji",
    "is_custom_emoji",
    "emoji_as_text",
]

_CUSTOM_TAG_RE = re.compile(r"<(?P<animated>a)?:(?P<name>[A-Za-z0-9_~]{1,32}):(?P<id>\d{15,22})>")
# Same thing with the angle brackets lost, e.g. ":name:123" or "a:name:123".
_CUSTOM_LOOSE_RE = re.compile(r"^(?P<animated>a)?:(?P<name>[A-Za-z0-9_~]{1,32}):(?P<id>\d{15,22})$")
_SHORTCODE_RE = re.compile(r":([A-Za-z0-9_+\-~]{1,64}):")
_BARE_NAME_RE = re.compile(r"^[A-Za-z0-9_~]{2,34}$")
_ID_RE = re.compile(r"^\d{15,22}$")
_DEDUPE_SUFFIX_RE = re.compile(r"~\d+$")
_FLAG_RE = re.compile(r"flag_([A-Za-z]{2})")
_TONE_RE = re.compile(r"(.+)_tone([1-5])")

# Zero-width characters that sneak in through copy & paste. The zero-width
# joiner (U+200D) and the variation selector (U+FE0F) are part of real emojis
# and must stay.
_INVISIBLE = dict.fromkeys(map(ord, "​⁠﻿"))

# Shortcodes Discord uses that the emoji library names differently.
_DISCORD_ALIASES = {
    "tools": "🛠️",
    "gear": "⚙️",
    "heart": "❤️",
    "thumbsup": "👍",
    "thumbsdown": "👎",
    "white_check_mark": "✅",
    "x": "❌",
}


def is_custom_emoji(value: Optional[str]) -> bool:
    return bool(value) and _CUSTOM_TAG_RE.fullmatch(value.strip()) is not None


def _canonical_custom(name: str, emoji_id: Union[int, str], animated: bool) -> str:
    return f"<{'a' if animated else ''}:{name}:{emoji_id}>"


def _fully_qualified(char: str) -> str:
    """Return the fully-qualified form (with variation selector) of an emoji.

    Discord lists emojis in their fully-qualified form, so "❤" becomes "❤️".
    """
    try:
        name = emoji_lib.demojize(char)
        if name != char:
            restored = emoji_lib.emojize(name)
            if restored != name and emoji_lib.is_emoji(restored):
                return restored
    except Exception:
        pass
    return char


def _first_unicode_emoji(text: str) -> Optional[str]:
    try:
        found = emoji_lib.emoji_list(text)
    except Exception:
        return None
    if not found:
        return None
    return _fully_qualified(found[0]["emoji"])


def _find_custom_by_name(name: str, pools: Iterable[Iterable]) -> Optional[str]:
    # Discord appends "~1", "~2", ... when two emojis share a name.
    names = [name]
    stripped = _DEDUPE_SUFFIX_RE.sub("", name)
    if stripped and stripped != name:
        names.append(stripped)

    for wanted in names:
        lowered = wanted.lower()
        for pool in pools:
            exact = None
            loose = None
            for candidate in pool or ():
                if candidate.name == wanted:
                    exact = candidate
                    break
                if loose is None and candidate.name.lower() == lowered:
                    loose = candidate
            hit = exact or loose
            if hit is not None:
                return _canonical_custom(hit.name, hit.id, bool(getattr(hit, "animated", False)))
    return None


def _lookup_shortcode(name: str) -> Optional[str]:
    alias = _DISCORD_ALIASES.get(name.lower())
    if alias:
        return alias
    for code in (f":{name}:", f":{name.lower()}:"):
        for language in ("alias", "en"):
            try:
                converted = emoji_lib.emojize(code, language=language)
            except Exception:
                continue
            if converted != code:
                return _first_unicode_emoji(converted)
    return None


def _shortcode_to_unicode(name: str) -> Optional[str]:
    """Resolve a standard-emoji shortcode the way Discord writes them."""
    # :flag_de: -> 🇩🇪
    flag = _FLAG_RE.fullmatch(name)
    if flag:
        candidate = "".join(chr(0x1F1E6 + ord(letter) - ord("a")) for letter in flag[1].lower())
        if emoji_lib.is_emoji(candidate):
            return candidate

    # :wave_tone3: -> 👋🏽
    tone = _TONE_RE.fullmatch(name)
    if tone:
        base = _lookup_shortcode(tone[1])
        if base:
            candidate = base.replace("\ufe0f", "") + chr(0x1F3FA + int(tone[2]))
            if emoji_lib.is_emoji(candidate):
                return candidate

    return _lookup_shortcode(name)


def parse_emoji(
    raw: Optional[str],
    guild: Optional[discord.Guild] = None,
    client: Optional[discord.Client] = None,
) -> Optional[str]:
    """Return the canonical emoji contained in ``raw`` or ``None``.

    ``guild`` and ``client`` are only used to resolve custom emojis that were
    given by name or by ID.
    """
    if not raw:
        return None
    text = str(raw).translate(_INVISIBLE).strip()
    if not text:
        return None

    # 1. A complete custom emoji tag anywhere in the text.
    match = _CUSTOM_TAG_RE.search(text) or _CUSTOM_LOOSE_RE.match(text.strip("<> "))
    if match:
        return _canonical_custom(match["name"], match["id"], bool(match["animated"]))

    # 2. A bare custom emoji ID.
    bare = text.strip("<>: ")
    if _ID_RE.fullmatch(bare):
        known = client.get_emoji(int(bare)) if client is not None else None
        if known is not None:
            return _canonical_custom(known.name, known.id, known.animated)
        # Discord identifies custom emojis by ID alone; the name is cosmetic.
        return _canonical_custom("emoji", bare, False)

    # 3. A Unicode emoji anywhere in the text ("<🩷>", "🩷 she/her", ...).
    unicode_emoji = _first_unicode_emoji(text)
    if unicode_emoji:
        return unicode_emoji

    guild_pool = getattr(guild, "emojis", None) or ()
    client_pool = getattr(client, "emojis", None) or ()

    # 4. Shortcodes: this server's custom emojis win, then standard emojis,
    #    then custom emojis from other servers the bot is in.
    for name in _SHORTCODE_RE.findall(text):
        found = _find_custom_by_name(name, (guild_pool,))
        if found:
            return found
        found = _shortcode_to_unicode(name)
        if found:
            return found
        found = _find_custom_by_name(name, (client_pool,))
        if found:
            return found

    # 5. A custom emoji name without colons.
    if _BARE_NAME_RE.fullmatch(bare):
        found = _find_custom_by_name(bare, (guild_pool, client_pool))
        if found:
            return found

    return None


def to_component_emoji(
    value: Optional[str],
    guild: Optional[discord.Guild] = None,
    client: Optional[discord.Client] = None,
) -> Optional[Union[str, discord.PartialEmoji]]:
    """Convert a stored emoji into a value for ``Button``/``SelectOption``.

    Stored values are re-parsed, so entries saved by older versions (for
    example ``<:pink_heart:>``, ``:flag_de:`` or a custom emoji saved by name)
    are repaired on the fly. Returns ``None`` when the value contains no usable
    emoji.
    """
    canonical = parse_emoji(value, guild, client)
    if not canonical:
        return None
    match = _CUSTOM_TAG_RE.fullmatch(canonical)
    if match:
        return discord.PartialEmoji(
            name=match["name"], id=int(match["id"]), animated=bool(match["animated"])
        )
    return canonical


def emoji_as_text(value: Optional[str], guild: Optional[discord.Guild] = None) -> str:
    """Emoji for use inside plain text such as embed descriptions.

    Falls back to the stored value so nothing silently disappears.
    """
    return parse_emoji(value, guild) or (value or "")

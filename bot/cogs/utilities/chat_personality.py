import asyncio
import logging
import os
import random
import re
import time
from collections import Counter
from typing import Optional

import discord
import emoji
from discord import app_commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color

try:
    from groq import AsyncGroq
except Exception:  # pragma: no cover - optional runtime dependency guard
    AsyncGroq = None


logger = logging.getLogger(__name__)

LANGUAGE_MODE_CHOICES = [
    app_commands.Choice(name="Auto detect", value="auto"),
    app_commands.Choice(name="Default English", value="default_en"),
]

CUSTOM_EMOJI_RE = re.compile(r"<a?:\w{2,32}:\d{17,20}>")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_']{3,}", re.UNICODE)
NON_LATIN_RE = re.compile(r"[\u0400-\u04FF\u0590-\u05FF\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u3400-\u9FFF]")

EN_HINTS = {
    "the", "and", "you", "that", "this", "with", "for", "are", "was", "have", "just", "why",
    "what", "when", "where", "mood", "same", "true", "clean", "point", "crazy", "valid",
}

DE_HINTS = {
    "und", "oder", "aber", "nicht", "doch", "dass", "war", "ist", "ein", "eine", "ich", "du",
    "wir", "ihr", "euch", "schon", "heute", "immer", "nie", "weil", "jetzt", "wieso", "warum",
}

PROFANITY_WORDS = {
    "arse", "ass", "bastard", "bitch", "bloody", "bullshit", "crap", "damn", "dick", "fucker",
    "fucking", "fuck", "hell", "idiot", "motherfucker", "nutte", "penner", "scheisse", "scheiße",
    "shit", "slut", "wanker", "whore",
}


class ChatPersonalityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._token_cache: dict[int, tuple[float, dict[str, list[dict]]]] = {}
        self._groq_client = None

        api_key = os.getenv("GROQ_API_KEY")
        if AsyncGroq is not None and api_key:
            self._groq_client = AsyncGroq(api_key=api_key)

    @commands.hybrid_group(
        name="chatpersona",
        description="Configure random chat personality behavior.",
    )
    @commands.guild_only()
    async def chatpersona_group(self, ctx: commands.Context):
        pass

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Nur Administratoren können diese Funktion konfigurieren.", ephemeral=True)
            return False
        return True

    @chatpersona_group.command(name="status", description="Show current chat personality settings")
    @commands.has_permissions(administrator=True)
    async def chatpersona_status(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return

        settings = await db.get_or_create_chat_personality_settings(ctx.guild.id)
        words = await db.get_chat_personality_top_tokens(ctx.guild.id, "word", limit=5)
        emojis = await db.get_chat_personality_top_tokens(ctx.guild.id, "emoji", limit=5)

        embed = discord.Embed(
            title="🧠 Chat Personality Status",
            color=await get_guild_color(ctx.guild.id),
        )
        embed.add_field(name="Enabled", value="Yes" if settings.get("enabled") else "No", inline=True)
        embed.add_field(name="Random chance", value=f"{int((settings.get('trigger_chance', 0.06) or 0.06) * 100)}%", inline=True)
        embed.add_field(name="Reply on bot replies", value="Yes" if settings.get("reply_always", True) else "No", inline=True)
        embed.add_field(name="Language mode", value=str(settings.get("language_mode", "auto")), inline=True)

        embed.add_field(name="Trait: Nice", value=str(settings.get("trait_nice", 65)), inline=True)
        embed.add_field(name="Trait: Romantic", value=str(settings.get("trait_romantic", 15)), inline=True)
        embed.add_field(name="Trait: Funny", value=str(settings.get("trait_funny", 45)), inline=True)
        embed.add_field(name="Trait: Chaotic", value=str(settings.get("trait_chaotic", 25)), inline=True)

        embed.add_field(name="Profanity allowed", value="Yes" if settings.get("allow_profanity") else "No", inline=True)
        embed.add_field(name="AI enabled", value="Yes" if settings.get("ai_enabled") else "No", inline=True)
        embed.add_field(name="AI chance", value=f"{int((settings.get('ai_chance', 0.15) or 0.15) * 100)}%", inline=True)

        embed.add_field(
            name="AI daily usage",
            value=f"{settings.get('ai_daily_used', 0)}/{settings.get('ai_daily_limit', 20)}",
            inline=True,
        )

        top_words = ", ".join(row["token_value"] for row in words) or "-"
        top_emojis = " ".join(row["token_value"] for row in emojis) or "-"
        embed.add_field(name="Top learned words", value=top_words[:1024], inline=False)
        embed.add_field(name="Top learned emojis", value=top_emojis[:1024], inline=False)

        await ctx.send(embed=embed, ephemeral=True)

    @chatpersona_group.command(name="enable", description="Enable or disable random chat messages")
    @app_commands.describe(enabled="Set to true to enable the feature")
    @commands.has_permissions(administrator=True)
    async def chatpersona_enable(self, ctx: commands.Context, enabled: bool):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, enabled=enabled)
        await ctx.send(f"✅ Chat personality {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @chatpersona_group.command(name="chance", description="Set random response chance (1-100%)")
    @app_commands.describe(percent="Chance in percent")
    @commands.has_permissions(administrator=True)
    async def chatpersona_chance(self, ctx: commands.Context, percent: app_commands.Range[int, 1, 100]):
        if not await self._require_admin(ctx):
            return
        chance = float(percent) / 100.0
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, trigger_chance=chance)
        await ctx.send(f"✅ Random chance set to {percent}%.", ephemeral=True)

    @chatpersona_group.command(name="language", description="Set language behavior for generated chat messages")
    @app_commands.describe(mode="auto = detect chat language, default_en = keep English by default")
    @app_commands.choices(mode=LANGUAGE_MODE_CHOICES)
    @commands.has_permissions(administrator=True)
    async def chatpersona_language(self, ctx: commands.Context, mode: str):
        if not await self._require_admin(ctx):
            return
        if mode not in {"auto", "default_en"}:
            await ctx.send("❌ Invalid mode. Use auto or default_en.", ephemeral=True)
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, language_mode=mode)
        await ctx.send(f"✅ Language mode set to `{mode}`.", ephemeral=True)

    @chatpersona_group.command(name="traits", description="Configure personality traits (0-100)")
    @app_commands.describe(
        nice="How friendly the bot should be",
        romantic="How romantic the bot should be",
        funny="How funny/silly the bot should be",
        chaotic="How random/chaotic the bot should be",
    )
    @commands.has_permissions(administrator=True)
    async def chatpersona_traits(
        self,
        ctx: commands.Context,
        nice: Optional[app_commands.Range[int, 0, 100]] = None,
        romantic: Optional[app_commands.Range[int, 0, 100]] = None,
        funny: Optional[app_commands.Range[int, 0, 100]] = None,
        chaotic: Optional[app_commands.Range[int, 0, 100]] = None,
    ):
        if not await self._require_admin(ctx):
            return
        updates = {}
        if nice is not None:
            updates["trait_nice"] = int(nice)
        if romantic is not None:
            updates["trait_romantic"] = int(romantic)
        if funny is not None:
            updates["trait_funny"] = int(funny)
        if chaotic is not None:
            updates["trait_chaotic"] = int(chaotic)

        if not updates:
            await ctx.send("❌ Bitte mindestens einen Trait angeben.", ephemeral=True)
            return

        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, **updates)
        await ctx.send("✅ Traits wurden aktualisiert.", ephemeral=True)

    @chatpersona_group.command(name="profanity", description="Allow or disallow profanity in generated messages")
    @app_commands.describe(enabled="Whether profanity is allowed")
    @commands.has_permissions(administrator=True)
    async def chatpersona_profanity(self, ctx: commands.Context, enabled: bool):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, allow_profanity=enabled)
        await ctx.send(f"✅ Profanity {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @chatpersona_group.command(name="replymode", description="Always reply when users reply to a bot message")
    @app_commands.describe(enabled="If true, replies to bot messages get an automatic response")
    @commands.has_permissions(administrator=True)
    async def chatpersona_replymode(self, ctx: commands.Context, enabled: bool):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, reply_always=enabled)
        await ctx.send(f"✅ Reply mode {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @chatpersona_group.command(name="ai", description="Configure limited AI refinement for generated chat")
    @app_commands.describe(
        enabled="Enable AI refinement",
        chance_percent="How often AI should refine generated messages (1-100)",
        daily_limit="Maximum AI refinements per day",
    )
    @commands.has_permissions(administrator=True)
    async def chatpersona_ai(
        self,
        ctx: commands.Context,
        enabled: bool,
        chance_percent: Optional[app_commands.Range[int, 1, 100]] = None,
        daily_limit: Optional[app_commands.Range[int, 1, 500]] = None,
    ):
        if not await self._require_admin(ctx):
            return

        updates = {"ai_enabled": enabled}
        if chance_percent is not None:
            updates["ai_chance"] = float(chance_percent) / 100.0
        if daily_limit is not None:
            updates["ai_daily_limit"] = int(daily_limit)

        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, **updates)

        msg = "✅ AI settings updated."
        if enabled and self._groq_client is None:
            msg += "\n⚠️ GROQ_API_KEY fehlt oder groq ist nicht verfügbar, daher bleibt AI faktisch inaktiv."
        await ctx.send(msg, ephemeral=True)

    @chatpersona_group.command(name="resetlearning", description="Delete learned words/emojis/gifs/stickers")
    @app_commands.describe(confirm="Type RESET to confirm")
    @commands.has_permissions(administrator=True)
    async def chatpersona_reset_learning(self, ctx: commands.Context, confirm: str):
        if not await self._require_admin(ctx):
            return
        if confirm.strip().upper() != "RESET":
            await ctx.send("❌ Bestätigung fehlt. Nutze confirm=RESET.", ephemeral=True)
            return
        await db.reset_chat_personality_learning(ctx.guild.id)
        self._token_cache.pop(ctx.guild.id, None)
        await ctx.send("✅ Learned data was reset.", ephemeral=True)

    @chatpersona_group.command(name="test", description="Generate a preview response using current settings")
    @commands.has_permissions(administrator=True)
    async def chatpersona_test(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        settings = await db.get_or_create_chat_personality_settings(ctx.guild.id)
        text = await self._build_response_text(
            guild_id=ctx.guild.id,
            author_name=ctx.author.display_name,
            incoming_text="test message",
            settings=settings,
        )
        if not settings.get("allow_profanity", False):
            text = self._sanitize_profanity(text)
        await ctx.send(f"🧪 Preview:\n{text[:1900]}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        try:
            settings = await db.get_or_create_chat_personality_settings(message.guild.id)
            await self._learn_from_message(message)

            if not settings.get("enabled", False):
                return

            is_reply_to_bot = await self._is_reply_to_bot_message(message)
            should_reply = bool(is_reply_to_bot and settings.get("reply_always", True))

            if not should_reply:
                chance = float(settings.get("trigger_chance", 0.06) or 0.06)
                should_reply = random.random() < max(0.0, min(1.0, chance))

            if not should_reply:
                return

            response_text = await self._build_response_text(
                guild_id=message.guild.id,
                author_name=message.author.display_name,
                incoming_text=message.content,
                settings=settings,
            )

            if not settings.get("allow_profanity", False):
                response_text = self._sanitize_profanity(response_text)

            if not response_text:
                return

            response_text = response_text[:2000]
            allowed_mentions = discord.AllowedMentions.none()

            if is_reply_to_bot:
                await message.reply(response_text, mention_author=False, allowed_mentions=allowed_mentions)
            else:
                await message.channel.send(response_text, allowed_mentions=allowed_mentions)

        except discord.Forbidden:
            return
        except discord.HTTPException:
            return
        except Exception as exc:
            logger.error("Chat personality on_message failed: %s", exc, exc_info=True)

    async def _is_reply_to_bot_message(self, message: discord.Message) -> bool:
        if not message.reference:
            return False

        replied = message.reference.resolved
        if isinstance(replied, discord.Message):
            return bool(replied.author and replied.author.id == self.bot.user.id)

        message_id = message.reference.message_id
        if not message_id:
            return False

        try:
            target = await message.channel.fetch_message(message_id)
            return bool(target.author and target.author.id == self.bot.user.id)
        except Exception:
            return False

    async def _learn_from_message(self, message: discord.Message):
        text = message.content or ""

        words = self._extract_words(text)
        word_counts = Counter(words)
        word_entries = list(word_counts.items())[:30]

        emojis = self._extract_emojis(text)
        emoji_entries = list(Counter(emojis).items())[:20]

        gifs = self._extract_gif_links(text)
        gif_entries = list(Counter(gifs).items())[:10]

        stickers = [s.name.strip() for s in (message.stickers or []) if getattr(s, "name", None)]
        sticker_entries = list(Counter(stickers).items())[:10]

        if word_entries:
            await db.bulk_increment_chat_personality_tokens(message.guild.id, "word", word_entries)
        if emoji_entries:
            await db.bulk_increment_chat_personality_tokens(message.guild.id, "emoji", emoji_entries)
        if gif_entries:
            await db.bulk_increment_chat_personality_tokens(message.guild.id, "gif", gif_entries)
        if sticker_entries:
            await db.bulk_increment_chat_personality_tokens(message.guild.id, "sticker", sticker_entries)

        if word_entries or emoji_entries or gif_entries or sticker_entries:
            self._token_cache.pop(message.guild.id, None)

    def _extract_words(self, text: str) -> list[str]:
        if not text:
            return []
        without_urls = URL_RE.sub(" ", text)
        words = [w.casefold() for w in WORD_RE.findall(without_urls)]
        return [w for w in words if not w.isdigit() and len(w) <= 28]

    def _extract_emojis(self, text: str) -> list[str]:
        if not text:
            return []
        items = CUSTOM_EMOJI_RE.findall(text)
        items.extend([entry["emoji"] for entry in emoji.emoji_list(text)])
        return items

    def _extract_gif_links(self, text: str) -> list[str]:
        if not text:
            return []
        links = URL_RE.findall(text)
        out = []
        for link in links:
            lower = link.lower()
            if lower.endswith(".gif") or "tenor.com" in lower or "giphy.com" in lower:
                out.append(link)
        return out

    async def _get_token_pool(self, guild_id: int) -> dict[str, list[dict]]:
        now = time.time()
        cached = self._token_cache.get(guild_id)
        if cached and cached[0] > now:
            return cached[1]

        words = await db.get_chat_personality_top_tokens(guild_id, "word", 120)
        emojis = await db.get_chat_personality_top_tokens(guild_id, "emoji", 40)
        gifs = await db.get_chat_personality_top_tokens(guild_id, "gif", 20)
        stickers = await db.get_chat_personality_top_tokens(guild_id, "sticker", 20)

        pool = {
            "word": words,
            "emoji": emojis,
            "gif": gifs,
            "sticker": stickers,
        }
        self._token_cache[guild_id] = (now + 120.0, pool)
        return pool

    def _weighted_pick(self, rows: list[dict], default: Optional[str] = None) -> Optional[str]:
        if not rows:
            return default
        choices = [row["token_value"] for row in rows]
        weights = [max(1, int(row.get("count", 1))) for row in rows]
        return random.choices(choices, weights=weights, k=1)[0]

    def _weighted_word_sample(self, rows: list[dict], sample_size: int) -> list[str]:
        if not rows or sample_size <= 0:
            return []

        pool = rows[:]
        sampled = []
        for _ in range(min(sample_size, len(pool))):
            choice = self._weighted_pick(pool)
            if not choice:
                continue
            sampled.append(choice)
            pool = [row for row in pool if row["token_value"] != choice]
        return sampled

    def _detect_language_mode(self, incoming_text: str, top_word_rows: list[dict]) -> str:
        incoming_words = self._extract_words(incoming_text)
        learned_words = [str(row.get("token_value", "")).casefold() for row in top_word_rows[:40]]
        all_words = [w.casefold() for w in incoming_words] + learned_words

        en_score = sum(1 for word in all_words if word in EN_HINTS)
        de_score = sum(1 for word in all_words if word in DE_HINTS)
        has_non_latin = bool(NON_LATIN_RE.search(incoming_text or ""))

        if de_score >= max(2, en_score + 2):
            return "de"
        if has_non_latin or (en_score <= 1 and de_score <= 1 and len(all_words) >= 4):
            return "mixed"
        return "en"

    def _finalize_single_message(self, text: str) -> str:
        cleaned = (text or "").replace("|", ",")
        cleaned = re.sub(r"\s*\n+\s*", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        if not cleaned:
            return ""
        first = cleaned[0].upper() + cleaned[1:]
        if first[-1] not in {"!", "?", "."} and not first.endswith("]"):
            first += "."
        return first[:2000]

    async def _build_response_text(self, guild_id: int, author_name: str, incoming_text: str, settings: dict) -> str:
        pool = await self._get_token_pool(guild_id)
        configured_mode = str(settings.get("language_mode", "auto") or "auto").strip().lower()
        if configured_mode == "default_en":
            language_mode = "en"
        else:
            language_mode = self._detect_language_mode(incoming_text, pool["word"])

        nice = int(settings.get("trait_nice", 65) or 65)
        romantic = int(settings.get("trait_romantic", 15) or 15)
        funny = int(settings.get("trait_funny", 45) or 45)
        chaotic = int(settings.get("trait_chaotic", 25) or 25)

        soft_openers_by_lang = {
            "en": [
                f"{author_name}, that was clean",
                "fair point, I can see that",
                "okay, that hit",
                "you are on a roll",
                "lowkey valid take",
            ],
            "de": [
                f"{author_name}, das war clean",
                "fairer punkt, fuehl ich",
                "okay, das hat gesessen",
                "du bist gerade im flow",
                "lowkey valider take",
            ],
            "mixed": [
                "that was kinda fire",
                "valid vibe right there",
                "okay, this chat is wild",
                "clean energy in here",
            ],
        }
        kind_bits_by_lang = {
            "en": ["you are doing great", "keep that energy", "love the vibe"],
            "de": ["du machst das stark", "behalt die energie", "ich feier den vibe"],
            "mixed": ["great vibe honestly", "solid energy", "clean mood"],
        }
        romantic_bits_by_lang = {
            "en": ["small heart moment", "romance arc unlocked"],
            "de": ["kleiner heart moment", "romance arc gestartet"],
            "mixed": ["heart mode on", "romance vibes detected"],
        }
        funny_bits_by_lang = {
            "en": ["plot twist incoming", "10/10 comedy timing", "this is cursed but good"],
            "de": ["plot twist incoming", "10/10 comedy timing", "cursed, aber gut"],
            "mixed": ["comedy timing unlocked", "chaotic but valid", "cursed in a good way"],
        }
        chaotic_bits_by_lang = {
            "en": ["chaos approved", "meta level 9000", "brain lag but we move"],
            "de": ["chaos genehmigt", "meta level 9000", "brain lag aber weiter"],
            "mixed": ["chaos mode accepted", "meta energy", "brain lag but still moving"],
        }

        opener = random.choice(soft_openers_by_lang[language_mode])
        if nice >= 70 and random.random() < 0.45:
            opener = f"{opener}, {random.choice(kind_bits_by_lang[language_mode])}"

        extras = []
        if romantic >= 60 and random.random() < romantic / 140:
            extras.append(random.choice(romantic_bits_by_lang[language_mode]))
        if funny >= 45 and random.random() < funny / 120:
            extras.append(random.choice(funny_bits_by_lang[language_mode]))
        if chaotic >= 55 and random.random() < chaotic / 130:
            extras.append(random.choice(chaotic_bits_by_lang[language_mode]))

        sampled_words = self._weighted_word_sample(pool["word"], sample_size=random.randint(1, 3))
        learned_fragment = ""
        if sampled_words and random.random() < 0.5:
            if chaotic >= 65 and len(sampled_words) > 1:
                random.shuffle(sampled_words)
            learned_fragment = " ".join(sampled_words)

        incoming_fragment = ""
        if incoming_text and random.random() < 0.25:
            incoming_words = self._extract_words(incoming_text)
            if incoming_words:
                incoming_fragment = random.choice(incoming_words[: min(8, len(incoming_words))])

        msg = opener
        if extras:
            msg = f"{msg}, {random.choice(extras)}"
        if learned_fragment:
            msg = f"{msg} {learned_fragment}"
        if incoming_fragment and incoming_fragment.casefold() not in msg.casefold():
            msg = f"{msg} {incoming_fragment}"

        emoji_pick = self._weighted_pick(pool["emoji"])
        if emoji_pick and random.random() < 0.9:
            msg = f"{msg} {emoji_pick}".strip()

        if not msg:
            msg = random.choice(["valid", "same", "I feel that", "okay yeah", "mood"])

        if random.random() < 0.18:
            gif_pick = self._weighted_pick(pool["gif"])
            if gif_pick:
                msg = f"{msg} {gif_pick}"[:2000]

        if random.random() < 0.12:
            sticker_pick = self._weighted_pick(pool["sticker"])
            if sticker_pick:
                msg = f"{msg} [sticker:{sticker_pick}]"

        msg = await self._maybe_refine_with_ai(
            guild_id=guild_id,
            msg=msg,
            incoming_text=incoming_text,
            settings=settings,
            traits={
                "nice": nice,
                "romantic": romantic,
                "funny": funny,
                "chaotic": chaotic,
            },
            language_mode=language_mode,
        )

        return self._finalize_single_message(msg)

    async def _maybe_refine_with_ai(
        self,
        guild_id: int,
        msg: str,
        incoming_text: str,
        settings: dict,
        traits: dict[str, int],
        language_mode: str,
    ) -> str:
        if not msg:
            return msg
        if self._groq_client is None:
            return msg
        if not settings.get("ai_enabled", True):
            return msg

        chance = float(settings.get("ai_chance", 0.15) or 0.15)
        if random.random() >= max(0.0, min(1.0, chance)):
            return msg

        can_use = await db.consume_chat_personality_ai_quota(guild_id)
        if not can_use:
            return msg

        system_prompt = (
            "You are writing a short Discord message for a bot personality. "
            "Keep it casual, human-like, and not obviously AI. "
            "Keep occasional rough edges and tiny nonsense allowed. "
            "Default to English unless the source chat is clearly another language. "
            "Return exactly one short message line without separators like '|', no bullet points, no multiple options."
        )

        user_prompt = (
            f"Incoming user message: {incoming_text or '-'}\n"
            f"Draft message: {msg}\n"
            f"Language mode: {language_mode}\n"
            f"Traits (0-100): {traits}\n"
            "Rewrite the draft only. Keep emojis/links/sticker tags if present."
        )

        try:
            completion = await asyncio.wait_for(
                self._groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.8,
                    max_tokens=90,
                    stream=False,
                ),
                timeout=5.5,
            )
            text = (completion.choices[0].message.content or "").strip()
            if text:
                return self._finalize_single_message(text)
        except Exception as exc:
            logger.debug("Chat personality AI refine skipped: %s", exc)
        return self._finalize_single_message(msg)

    def _sanitize_profanity(self, text: str) -> str:
        if not text:
            return text

        def repl(match: re.Match):
            word = match.group(0)
            return "*" * len(word)

        pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(PROFANITY_WORDS, key=len, reverse=True)) + r")\b", re.IGNORECASE)
        return pattern.sub(repl, text)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatPersonalityCog(bot))

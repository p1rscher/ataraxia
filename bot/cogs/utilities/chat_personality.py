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

BLACKLIST_TARGET_CHOICES = [
    app_commands.Choice(name="Text", value="text"),
    app_commands.Choice(name="GIF", value="gif"),
    app_commands.Choice(name="Sticker", value="sticker"),
    app_commands.Choice(name="All", value="all"),
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
        self._last_generated_parts: dict[int, dict[str, str]] = {}
        self._last_spontaneous_message_at: dict[int, float] = {}
        self._last_sticker_message_at: dict[int, float] = {}
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

    @chatpersona_group.group(name="blacklist", description="Manage channel blacklists for text, GIF, and sticker outputs")
    @commands.has_permissions(administrator=True)
    async def blacklist_group(self, ctx: commands.Context):
        pass

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
        embed.add_field(name="Text chance", value=f"{int((settings.get('trigger_chance', 0.06) or 0.06) * 100)}%", inline=True)
        embed.add_field(name="GIF chance", value=f"{int((settings.get('gif_chance', 0.08) or 0.08) * 100)}%", inline=True)
        embed.add_field(name="Sticker chance", value=f"{int((settings.get('sticker_chance', 0.08) or 0.08) * 100)}%", inline=True)
        embed.add_field(name="Cooldown per channel", value=f"{int(settings.get('cooldown_seconds', 180) or 180)}s", inline=True)
        embed.add_field(name="Sticker cooldown", value=f"{int(settings.get('sticker_cooldown_seconds', 600) or 600)}s", inline=True)
        embed.add_field(name="Reply on bot replies", value="Yes" if settings.get("reply_always", True) else "No", inline=True)
        embed.add_field(name="Language mode", value=str(settings.get("language_mode", "auto")), inline=True)

        embed.add_field(name="Trait: Nice", value=str(settings.get("trait_nice", 65)), inline=True)
        embed.add_field(name="Trait: Romantic", value=str(settings.get("trait_romantic", 15)), inline=True)
        embed.add_field(name="Trait: Funny", value=str(settings.get("trait_funny", 45)), inline=True)
        embed.add_field(name="Trait: Chaotic", value=str(settings.get("trait_chaotic", 25)), inline=True)

        embed.add_field(name="Profanity allowed", value="Yes" if settings.get("allow_profanity") else "No", inline=True)
        embed.add_field(name="AI enabled", value="Yes" if settings.get("ai_enabled") else "No", inline=True)
        embed.add_field(name="AI chance", value=f"{int((settings.get('ai_chance', 0.75) or 0.75) * 100)}%", inline=True)

        embed.add_field(
            name="AI daily usage",
            value=f"{settings.get('ai_daily_used', 0)}/{settings.get('ai_daily_limit', 5000)}",
            inline=True,
        )

        top_words = ", ".join(row["token_value"] for row in words) or "-"
        top_emojis = " ".join(row["token_value"] for row in emojis) or "-"
        blocked_channels = self._format_blacklist_targets(ctx.guild, settings)
        embed.add_field(name="Top learned words", value=top_words[:1024], inline=False)
        embed.add_field(name="Top learned emojis", value=top_emojis[:1024], inline=False)
        embed.add_field(name="Blacklisted channels", value=blocked_channels[:1024], inline=False)

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
        await ctx.send(f"✅ Text chance set to {percent}%.", ephemeral=True)

    @chatpersona_group.command(name="gifchance", description="Set chance for adding a GIF link")
    @app_commands.describe(percent="Chance in percent")
    @commands.has_permissions(administrator=True)
    async def chatpersona_gif_chance(self, ctx: commands.Context, percent: app_commands.Range[int, 0, 100]):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, gif_chance=float(percent) / 100.0)
        await ctx.send(f"✅ GIF chance set to {percent}%.", ephemeral=True)

    @chatpersona_group.command(name="stickerchance", description="Set chance for sending a sticker")
    @app_commands.describe(percent="Chance in percent")
    @commands.has_permissions(administrator=True)
    async def chatpersona_sticker_chance(self, ctx: commands.Context, percent: app_commands.Range[int, 0, 100]):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, sticker_chance=float(percent) / 100.0)
        await ctx.send(f"✅ Sticker chance set to {percent}%.", ephemeral=True)

    @chatpersona_group.command(name="cooldown", description="Set cooldown for spontaneous random chat messages")
    @app_commands.describe(seconds="Minimum seconds between spontaneous bot messages")
    @commands.has_permissions(administrator=True)
    async def chatpersona_cooldown(self, ctx: commands.Context, seconds: app_commands.Range[int, 0, 3600]):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, cooldown_seconds=int(seconds))
        await ctx.send(f"✅ Chat personality cooldown set to {int(seconds)}s.", ephemeral=True)

    @chatpersona_group.command(name="stickercooldown", description="Set cooldown for spontaneous sticker messages")
    @app_commands.describe(seconds="Minimum seconds between sticker sends in the same channel")
    @commands.has_permissions(administrator=True)
    async def chatpersona_sticker_cooldown(self, ctx: commands.Context, seconds: app_commands.Range[int, 0, 7200]):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await db.update_chat_personality_settings(ctx.guild.id, sticker_cooldown_seconds=int(seconds))
        await ctx.send(f"✅ Sticker cooldown set to {int(seconds)}s.", ephemeral=True)

    @blacklist_group.command(name="add", description="Block one channel for text, GIF, sticker, or all outputs")
    @app_commands.describe(channel="Channel to blacklist", target="Which output type should be blocked")
    @app_commands.choices(target=BLACKLIST_TARGET_CHOICES)
    async def blacklist_add(self, ctx: commands.Context, channel: discord.TextChannel, target: str):
        if not await self._require_admin(ctx):
            return
        settings = await db.get_or_create_chat_personality_settings(ctx.guild.id)
        targets = self._targets_from_choice(target)
        updates = {}
        already_blocked = []
        added = []
        for name in targets:
            key = self._blacklist_key(name)
            channel_ids = self._get_blacklisted_channel_ids(settings, name)
            if channel.id in channel_ids:
                already_blocked.append(name)
                continue
            channel_ids.append(channel.id)
            updates[key] = channel_ids
            added.append(name)
        if updates:
            await db.update_chat_personality_settings(ctx.guild.id, **updates)
        if added and not already_blocked:
            await ctx.send(f"✅ {channel.mention} was blacklisted for: {', '.join(added)}.", ephemeral=True)
            return
        if added:
            await ctx.send(f"✅ {channel.mention} was blacklisted for: {', '.join(added)}. Already blocked: {', '.join(already_blocked)}.", ephemeral=True)
            return
        await ctx.send(f"ℹ️ {channel.mention} is already blacklisted for: {', '.join(already_blocked)}.", ephemeral=True)

    @blacklist_group.command(name="remove", description="Remove one channel from a text, GIF, sticker, or all blacklist")
    @app_commands.describe(channel="Channel to un-blacklist", target="Which output type should be unblocked")
    @app_commands.choices(target=BLACKLIST_TARGET_CHOICES)
    async def blacklist_remove(self, ctx: commands.Context, channel: discord.TextChannel, target: str):
        if not await self._require_admin(ctx):
            return
        settings = await db.get_or_create_chat_personality_settings(ctx.guild.id)
        targets = self._targets_from_choice(target)
        updates = {}
        removed = []
        missing = []
        for name in targets:
            key = self._blacklist_key(name)
            channel_ids = self._get_blacklisted_channel_ids(settings, name)
            if channel.id not in channel_ids:
                missing.append(name)
                continue
            channel_ids.remove(channel.id)
            updates[key] = channel_ids
            removed.append(name)
        if updates:
            await db.update_chat_personality_settings(ctx.guild.id, **updates)
        if removed and not missing:
            await ctx.send(f"✅ {channel.mention} was removed from: {', '.join(removed)}.", ephemeral=True)
            return
        if removed:
            await ctx.send(f"✅ {channel.mention} was removed from: {', '.join(removed)}. Not blocked in: {', '.join(missing)}.", ephemeral=True)
            return
        await ctx.send(f"ℹ️ {channel.mention} is not blacklisted for: {', '.join(missing)}.", ephemeral=True)

    @blacklist_group.command(name="list", description="List all blacklisted channels for text, GIF, and sticker outputs")
    async def blacklist_list(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return
        settings = await db.get_or_create_chat_personality_settings(ctx.guild.id)
        await ctx.send(
            f"**Chat blacklists:** {self._format_blacklist_targets(ctx.guild, settings)}",
            ephemeral=True,
        )

    @blacklist_group.command(name="clear", description="Clear blacklisted channels for one output type or all")
    @app_commands.describe(target="Which output type blacklist should be cleared")
    @app_commands.choices(target=BLACKLIST_TARGET_CHOICES)
    async def blacklist_clear(self, ctx: commands.Context, target: str):
        if not await self._require_admin(ctx):
            return
        await db.get_or_create_chat_personality_settings(ctx.guild.id)
        updates = {self._blacklist_key(name): [] for name in self._targets_from_choice(target)}
        await db.update_chat_personality_settings(ctx.guild.id, **updates)
        await ctx.send(f"✅ Cleared blacklist for: {', '.join(self._targets_from_choice(target))}.", ephemeral=True)

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
            channel_id=ctx.channel.id,
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

            text_blocked = self._is_channel_blacklisted(settings, "text", message.channel.id)

            is_reply_to_bot = await self._is_reply_to_bot_message(message)
            should_reply = bool(is_reply_to_bot and settings.get("reply_always", True) and not text_blocked)

            if not should_reply:
                if text_blocked:
                    return
                cooldown_seconds = max(0, int(settings.get("cooldown_seconds", 180) or 180))
                last_sent_at = self._last_spontaneous_message_at.get(message.channel.id, 0.0)
                if cooldown_seconds > 0 and time.time() - last_sent_at < cooldown_seconds:
                    return
                chance = float(settings.get("trigger_chance", 0.06) or 0.06)
                should_reply = random.random() < max(0.0, min(1.0, chance))

            if not should_reply:
                return

            response_text = await self._build_response_text(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                author_name=message.author.display_name,
                incoming_text=message.content,
                settings=settings,
            )
            sticker = await self._pick_sticker_for_message(
                message.guild,
                message.channel.id,
                message.content,
                settings,
            )

            if not settings.get("allow_profanity", False):
                response_text = self._sanitize_profanity(response_text)

            if not response_text and sticker is None:
                return

            allowed_mentions = discord.AllowedMentions.none()

            if response_text:
                response_text = response_text[:2000]
                if is_reply_to_bot:
                    await message.reply(response_text, mention_author=False, allowed_mentions=allowed_mentions)
                else:
                    await message.channel.send(response_text, allowed_mentions=allowed_mentions)

            if sticker is not None:
                try:
                    await message.channel.send(stickers=[sticker], allowed_mentions=allowed_mentions)
                    self._last_sticker_message_at[message.channel.id] = time.time()
                except TypeError:
                    logger.debug("Sticker sending is not supported by the current discord.py runtime")

            if not is_reply_to_bot:
                self._last_spontaneous_message_at[message.channel.id] = time.time()

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

        stickers = []
        for sticker in message.stickers or []:
            token = self._serialize_sticker_token(sticker)
            if token:
                stickers.append(token)
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

    def _targets_from_choice(self, target: str) -> list[str]:
        if target == "all":
            return ["text", "gif", "sticker"]
        return [target]

    def _blacklist_key(self, target: str) -> str:
        return f"{target}_blocked_channel_ids"

    def _get_blacklisted_channel_ids(self, settings: dict, target: str) -> list[int]:
        raw_ids = settings.get(self._blacklist_key(target)) or []
        return [int(channel_id) for channel_id in raw_ids if str(channel_id).isdigit()]

    def _is_channel_blacklisted(self, settings: dict, target: str, channel_id: int) -> bool:
        return channel_id in self._get_blacklisted_channel_ids(settings, target)

    def _format_channel_mentions(self, guild: discord.Guild, channel_ids: list[int]) -> str:
        if not channel_ids:
            return "-"
        labels = []
        for channel_id in channel_ids[:10]:
            channel = guild.get_channel(channel_id)
            labels.append(channel.mention if channel else f"Deleted channel ({channel_id})")
        if len(channel_ids) > 10:
            labels.append(f"+{len(channel_ids) - 10} more")
        return ", ".join(labels)

    def _format_blacklist_targets(self, guild: discord.Guild, settings: dict) -> str:
        text_channels = self._format_channel_mentions(guild, self._get_blacklisted_channel_ids(settings, "text"))
        gif_channels = self._format_channel_mentions(guild, self._get_blacklisted_channel_ids(settings, "gif"))
        sticker_channels = self._format_channel_mentions(guild, self._get_blacklisted_channel_ids(settings, "sticker"))
        return f"Text: {text_channels}\nGIF: {gif_channels}\nSticker: {sticker_channels}"

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

    def _pick_varied_text(self, guild_id: int, key: str, options: list[str]) -> str:
        if not options:
            return ""

        memory = self._last_generated_parts.setdefault(guild_id, {})
        last_value = memory.get(key)
        pool = [option for option in options if option != last_value] or options
        choice = random.choice(pool)
        memory[key] = choice
        return choice

    def _weighted_pick_varied_token(self, guild_id: int, key: str, rows: list[dict], default: Optional[str] = None) -> Optional[str]:
        if not rows:
            return default

        memory = self._last_generated_parts.setdefault(guild_id, {})
        last_value = memory.get(key)
        if len(rows) > 1 and last_value:
            filtered = [row for row in rows if row.get("token_value") != last_value]
            if filtered:
                rows = filtered

        choice = self._weighted_pick(rows, default=default)
        if choice:
            memory[key] = choice
        return choice

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

    def _serialize_sticker_token(self, sticker: object) -> Optional[str]:
        sticker_id = getattr(sticker, "id", None)
        sticker_name = (getattr(sticker, "name", "") or "").strip()
        if not sticker_id or not sticker_name:
            return None
        return f"{int(sticker_id)}:{sticker_name}"

    def _resolve_sticker_token(self, guild: discord.Guild, token: str) -> Optional[discord.GuildSticker]:
        if not token:
            return None

        sticker_id: Optional[int] = None
        sticker_name = token.strip()
        if ":" in token:
            raw_id, raw_name = token.split(":", 1)
            if raw_id.isdigit():
                sticker_id = int(raw_id)
                sticker_name = raw_name.strip() or sticker_name

        if sticker_id is not None:
            sticker = guild.get_sticker(sticker_id)
            if isinstance(sticker, discord.GuildSticker):
                return sticker

        lowered = sticker_name.casefold()
        for sticker in guild.stickers:
            if getattr(sticker, "name", "").casefold() == lowered:
                return sticker
        return None

    async def _pick_sticker_for_message(
        self,
        guild: discord.Guild,
        channel_id: int,
        incoming_text: str,
        settings: dict,
    ) -> Optional[discord.GuildSticker]:
        pool = await self._get_token_pool(guild.id)
        sticker_rows = pool.get("sticker") or []
        if not sticker_rows:
            return None

        if self._is_channel_blacklisted(settings, "sticker", channel_id):
            return None

        sticker_cooldown_seconds = max(0, int(settings.get("sticker_cooldown_seconds", 600) or 600))
        last_sticker_at = self._last_sticker_message_at.get(channel_id, 0.0)
        if sticker_cooldown_seconds > 0 and time.time() - last_sticker_at < sticker_cooldown_seconds:
            return None

        incoming_has_emoji = bool(self._extract_emojis(incoming_text))
        base_chance = float(settings.get("sticker_chance", 0.08) or 0.08)
        if incoming_has_emoji:
            base_chance = min(1.0, base_chance * 1.75)
        if random.random() >= base_chance:
            return None

        token = self._weighted_pick_varied_token(guild.id, "sticker", sticker_rows)
        if not token:
            return None
        return self._resolve_sticker_token(guild, token)

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

    async def _build_response_text(self, guild_id: int, channel_id: int, author_name: str, incoming_text: str, settings: dict) -> str:
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
        incoming_words = self._extract_words(incoming_text)
        incoming_emojis = self._extract_emojis(incoming_text)

        sampled_words = self._weighted_word_sample(pool["word"], sample_size=random.randint(2, 5))
        learned_fragment = ""
        if sampled_words and random.random() < 0.55:
            if chaotic >= 65 and len(sampled_words) > 1:
                random.shuffle(sampled_words)
            learned_fragment = " ".join(sampled_words)

        incoming_fragment = ""
        if incoming_words and random.random() < 0.35:
            incoming_fragment = random.choice(incoming_words[: min(10, len(incoming_words))])

        emoji_rows = pool["emoji"]
        emoji_pick = None
        emoji_chance = 0.0
        if emoji_rows:
            if incoming_emojis:
                emoji_chance = 0.5
            elif len(emoji_rows) == 1:
                emoji_chance = 0.12
            else:
                emoji_chance = 0.22

        if emoji_chance > 0 and random.random() < emoji_chance:
            emoji_pick = self._weighted_pick_varied_token(guild_id, "emoji", emoji_rows)

        ai_seed = self._build_ai_seed(
            author_name=author_name,
            incoming_text=incoming_text,
            learned_fragment=learned_fragment,
            incoming_fragment=incoming_fragment,
            emoji_pick=emoji_pick,
            traits={
                "nice": nice,
                "romantic": romantic,
                "funny": funny,
                "chaotic": chaotic,
            },
            language_mode=language_mode,
        )
        ai_text = await self._try_ai_filler(
            guild_id=guild_id,
            seed=ai_seed,
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
        if ai_text:
            msg = ai_text
        else:
            msg = ""

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

        if not msg:
            opener = self._pick_varied_text(guild_id, "opener", soft_openers_by_lang[language_mode])
            if nice >= 70 and random.random() < 0.25:
                opener = f"{opener}, {self._pick_varied_text(guild_id, 'kind', kind_bits_by_lang[language_mode])}"

            extras = []
            if romantic >= 60 and random.random() < romantic / 180:
                extras.append(self._pick_varied_text(guild_id, "romantic", romantic_bits_by_lang[language_mode]))
            if funny >= 45 and random.random() < funny / 150:
                extras.append(self._pick_varied_text(guild_id, "funny", funny_bits_by_lang[language_mode]))
            if chaotic >= 55 and random.random() < chaotic / 160:
                extras.append(self._pick_varied_text(guild_id, "chaotic", chaotic_bits_by_lang[language_mode]))

            structure_mode = random.choices(
                ["opener", "learned", "reactive", "minimal"],
                weights=[20, 25, 30, 25],
                k=1,
            )[0]

            if structure_mode == "learned" and learned_fragment:
                msg = learned_fragment
                if extras and random.random() < 0.35:
                    msg = f"{msg}, {extras[0]}"
                if random.random() < 0.35:
                    msg = f"{opener}, {msg}"
            elif structure_mode == "reactive" and incoming_fragment:
                msg = f"{opener}, {incoming_fragment}"
                if extras and random.random() < 0.3:
                    msg = f"{msg}, {extras[0]}"
            elif structure_mode == "minimal":
                minimal_pool = [learned_fragment, incoming_fragment, opener, *(extras[:1] if extras else [])]
                msg = random.choice([part for part in minimal_pool if part] or [opener])
            else:
                msg = opener
                if learned_fragment and random.random() < 0.25:
                    msg = f"{msg} {learned_fragment}"
                if extras and random.random() < 0.25:
                    msg = f"{msg}, {extras[0]}"

            if emoji_pick:
                msg = f"{msg} {emoji_pick}".strip()

        if not msg:
            msg = random.choice(["valid", "same", "I feel that", "okay yeah", "mood"])

        gif_chance = float(settings.get("gif_chance", 0.08) or 0.08)
        if not self._is_channel_blacklisted(settings, "gif", channel_id):
            if any("gif" in word.casefold() for word in incoming_words) or "tenor.com" in incoming_text.lower() or "giphy.com" in incoming_text.lower():
                gif_chance = min(1.0, gif_chance * 2.5)
        else:
            gif_chance = 0.0
        if random.random() < gif_chance:
            gif_pick = self._weighted_pick_varied_token(guild_id, "gif", pool["gif"])
            if gif_pick:
                msg = f"{msg} {gif_pick}"[:2000]

        return self._finalize_single_message(msg)

    def _build_ai_seed(
        self,
        *,
        author_name: str,
        incoming_text: str,
        learned_fragment: str,
        incoming_fragment: str,
        emoji_pick: Optional[str],
        traits: dict[str, int],
        language_mode: str,
    ) -> str:
        pieces = []
        if incoming_fragment:
            pieces.append(f"reply hook: {incoming_fragment}")
        if learned_fragment:
            pieces.append(f"learned words: {learned_fragment}")
        if emoji_pick:
            pieces.append(f"emoji: {emoji_pick}")
        if incoming_text:
            pieces.append(f"source vibe: {incoming_text[:120]}")
        pieces.append(f"addressed user: {author_name}")
        pieces.append(f"language: {language_mode}")
        pieces.append(
            "traits: " + ", ".join(f"{key}={value}" for key, value in traits.items())
        )
        return " ; ".join(piece for piece in pieces if piece)

    async def _try_ai_filler(
        self,
        *,
        guild_id: int,
        seed: str,
        incoming_text: str,
        settings: dict,
        traits: dict[str, int],
        language_mode: str,
    ) -> Optional[str]:
        if not seed:
            return None
        if self._groq_client is None:
            return None
        if not settings.get("ai_enabled", True):
            return None

        chance = float(settings.get("ai_chance", 0.75) or 0.75)
        if random.random() >= max(0.0, min(1.0, chance)):
            return None

        can_use = await db.consume_chat_personality_ai_quota(guild_id)
        if not can_use:
            return None

        system_prompt = (
            "You are writing one casual Discord line for a bot personality. "
            "Use the provided seed as raw material, not as a rigid template. "
            "Sound human, slightly messy, not polished, not robotic. "
            "Default to English unless the chat is clearly another language. "
            "Do not output multiple variants, labels, bullet points, or explanations."
        )
        user_prompt = (
            f"Incoming user message: {incoming_text or '-'}\n"
            f"Seed material: {seed}\n"
            f"Language mode: {language_mode}\n"
            f"Traits (0-100): {traits}\n"
            "Write exactly one short reply line."
        )

        try:
            completion = await asyncio.wait_for(
                self._groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.95,
                    max_tokens=90,
                    stream=False,
                ),
                timeout=6.0,
            )
            text = (completion.choices[0].message.content or "").strip()
            if text:
                return self._finalize_single_message(text)
        except Exception as exc:
            logger.debug("Chat personality AI filler skipped: %s", exc)
        return None

    async def _maybe_refine_with_ai(
        self,
        guild_id: int,
        msg: str,
        incoming_text: str,
        settings: dict,
        traits: dict[str, int],
        language_mode: str,
    ) -> str:
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

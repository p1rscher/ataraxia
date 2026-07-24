# cogs/utilities/translator.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import os
from typing import Optional
from collections import defaultdict
from datetime import datetime, timezone
from groq import AsyncGroq

from deep_translator import GoogleTranslator
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# Fetch supported languages once to avoid repeated API calls
try:
    SUPPORTED_LANGUAGES = GoogleTranslator().get_supported_languages(as_dict=True)
    VALID_CODES = list(SUPPORTED_LANGUAGES.values())
except Exception as e:
    logger.error(f"Failed to fetch supported languages from GoogleTranslator: {e}")
    VALID_CODES = []
    SUPPORTED_LANGUAGES = {}

class TranslatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY')) if os.getenv('GROQ_API_KEY') else None
        self.daily_ai_translations = defaultdict(lambda: {'count': 0, 'date': None})
        self.tier_settings = {
            'free': 30,
            'premium': 70,
            'premium_plus': 100
        }

    @commands.hybrid_command(name="tr", description="Translate a message")
    @app_commands.describe(
        original_language="Optional original language code (e.g. en, fr, de)",
        destination_language="Optional destination language code",
        ai_powered="Enable AI-powered translation using Groq (limited daily uses)",
        text="The text to translate. (Optional if replying to a message)"
    )
    @app_commands.choices(ai_powered=[
        app_commands.Choice(name="Yes (Use AI)", value="true"),
        app_commands.Choice(name="No (Standard)", value="false")
    ])
    async def tr(self, ctx: commands.Context, original_language: Optional[str] = None, destination_language: Optional[str] = None, ai_powered: Optional[str] = None, *, text: Optional[str] = None):
        if not VALID_CODES:
            await ctx.send("❌ Translator service is currently unavailable.", ephemeral=True)
            return

        # Check for replied message
        replied_message = None
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.NotFound:
                pass

        source_lang = 'auto'
        dest_lang = None
        text_to_translate = ""
        use_ai = False

        if ctx.interaction is None:
            # Prefix command: reconstruct the text and parse manually
            parts = [p for p in (original_language, destination_language, ai_powered, text) if p is not None]
            full_text = " ".join(parts)
            
            words = full_text.split()
            if len(words) >= 1 and words[0].lower() in VALID_CODES:
                if len(words) >= 2 and words[1].lower() in VALID_CODES:
                    source_lang = words[0].lower()
                    dest_lang = words[1].lower()
                    text_to_translate = " ".join(words[2:])
                else:
                    # 1 valid code provided -> treat as destination language, source is auto
                    dest_lang = words[0].lower()
                    text_to_translate = " ".join(words[1:])
            else:
                text_to_translate = full_text
        else:
            # Slash command: use explicit parameters
            if original_language and original_language.lower() in VALID_CODES:
                source_lang = original_language.lower()
            if destination_language and destination_language.lower() in VALID_CODES:
                dest_lang = destination_language.lower()
            if ai_powered == "true":
                use_ai = True
            if text:
                text_to_translate = text

        # If no text to translate was parsed but there is a replied message, use the replied message content
        if not text_to_translate.strip() and replied_message:
            text_to_translate = replied_message.content

        if not text_to_translate.strip():
            await ctx.send("❌ Please provide text to translate or reply to a message.", ephemeral=True)
            return

        # Determine default destination language if not specified
        if not dest_lang:
            if ctx.guild:
                dest_lang = await db.get_default_language(ctx.guild.id)
                if not dest_lang:
                    await ctx.send("❌ The server administrator has not set a default translation language. Please use `/trset` to set it up, or specify a destination language in the command.", ephemeral=True)
                    return
            else:
                dest_lang = 'en' # Default for DMs

        # Make sure default language is valid
        if dest_lang not in VALID_CODES:
            await ctx.send(f"❌ The server's default language (`{dest_lang}`) is invalid. Please update it with `/trset`.", ephemeral=True)
            return

        # Check AI Limits
        if use_ai:
            if not getattr(self, 'client', None):
                await ctx.send("❌ AI translation is not configured (missing API key).", ephemeral=True)
                return

            user_id = ctx.author.id
            today = datetime.now(timezone.utc).date()
            user_usage = self.daily_ai_translations[user_id]
            
            if user_usage['date'] != today:
                user_usage['count'] = 0
                user_usage['date'] = today

            tier = await db.get_user_premium_tier(user_id)
            limit = self.tier_settings.get(tier, 30)

            if user_usage['count'] >= limit:
                await ctx.send(f"❌ **Daily AI Translation limit reached!**\nYou've used **{user_usage['count']}/{limit}** requests today.\nUse standard translation or wait until midnight UTC.", ephemeral=True)
                return

        # Defer the response since translation might take a moment
        await ctx.defer()

        # Resolve language names
        source_name = "Auto"
        if source_lang != 'auto':
            source_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == source_lang), source_lang).title()
        dest_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == dest_lang), dest_lang).title()

        # Perform translation
        try:
            if use_ai:
                system_prompt = f"You are an expert translator. Translate the following text from {source_name} to {dest_name}. Respond ONLY with the translated text, nothing else. No conversational filler or explanations."
                
                completion = await self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text_to_translate}
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                )
                translated = completion.choices[0].message.content.strip()
                self.daily_ai_translations[ctx.author.id]['count'] += 1
            else:
                translator = GoogleTranslator(source=source_lang, target=dest_lang)
                translated = await asyncio.to_thread(translator.translate, text_to_translate)
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            await ctx.send("❌ Failed to translate the message. The translation service might be temporarily unavailable.", ephemeral=True)
            return

        # Prepare embed
        guild_color = await get_guild_color(ctx.guild.id) if ctx.guild else discord.Color.blue()
        
        embed = discord.Embed(
            description=f"**Original:**\n{text_to_translate}\n\n**Translation:**\n{translated}",
            color=guild_color
        )
        
        footer_text = f"Translated from {source_name} to {dest_name}"
        if use_ai:
            tier = await db.get_user_premium_tier(ctx.author.id)
            limit = self.tier_settings.get(tier, 30)
            footer_text += f" | AI Powered (Llama 3.3) • {self.daily_ai_translations[ctx.author.id]['count']}/{limit} today"
            
        embed.set_footer(text=footer_text)
        
        if replied_message:
            embed.set_author(name=replied_message.author.display_name, icon_url=replied_message.author.display_avatar.url if replied_message.author.display_avatar else None)
        else:
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trset", description="Set the default server language for translations")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(language="The language code (e.g. en, de, fr, es)")
    async def trset(self, ctx: commands.Context, language: str):
        if not VALID_CODES:
            await ctx.send("❌ Translator service is currently unavailable.", ephemeral=True)
            return

        language = language.lower()
        if language not in VALID_CODES:
            example_codes = ", ".join(VALID_CODES[:5])
            await ctx.send(f"❌ Invalid language code. Supported examples: `{example_codes}`...", ephemeral=True)
            return
            
        await db.set_default_language(ctx.guild.id, language)
        lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == language), language).title()
        
        embed = discord.Embed(
            title="Settings Updated",
            description=f"✅ Default server language for translations has been set to **{lang_name}** (`{language}`).",
            color=await get_guild_color(ctx.guild.id)
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TranslatorCog(bot))

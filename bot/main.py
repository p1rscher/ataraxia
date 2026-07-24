# main.py

"""
Ataraxia Discord Bot
Copyright (c) 2025 p1rscher
Licensed under the MIT License - see LICENSE file for details.
"""

import os
import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
from core.counting_cache import CountingCacheManager
from core.leveling_cache import LevelingCacheManager
from core.message_cache import MessageCacheManager
from utils import ProcessLock, grant_voice_xp, update_stats_json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Select database based on environment variable
load_dotenv()
if os.getenv("DATABASE_URL"):
    from core import database_pg as db
    logger.info("Using PostgreSQL database")
else:
    logger.error("Failed to load database module")
    quit(1)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

DEFAULT_PREFIXES = ["Atx.", "atx."]

# In-memory prefix cache: guild_id -> list of prefix dicts
_prefix_cache: dict[int, list[dict]] = {}

async def get_prefix(bot_instance: commands.Bot, message: discord.Message) -> list[str]:
    """Dynamic prefix resolver. Returns the guild's custom prefixes and the default."""
    # Always include mentions
    valid_prefixes = commands.when_mentioned(bot_instance, message)
    
    if not message.guild:
        valid_prefixes.extend(DEFAULT_PREFIXES)
        return valid_prefixes

    guild_id = message.guild.id

    # Check cache first
    if guild_id not in _prefix_cache:
        # Query DB and cache the result
        try:
            prefixes = await db.get_guild_prefixes(guild_id)
            _prefix_cache[guild_id] = prefixes
        except Exception:
            _prefix_cache[guild_id] = []

    custom_prefixes = _prefix_cache[guild_id]
    
    valid_prefixes.extend(DEFAULT_PREFIXES)
    
    content = message.content
    for p in custom_prefixes:
        prefix_str = p['prefix']
        if p['case_insensitive']:
            if content.lower().startswith(prefix_str.lower()):
                # Yield the exact casing the user typed to allow discord.py to strip it
                valid_prefixes.append(content[:len(prefix_str)])
        else:
            valid_prefixes.append(prefix_str)

    return valid_prefixes

class AtaraxiaContext(commands.Context):
    @staticmethod
    def _normalize_prefix_response_kwargs(kwargs):
        normalized = dict(kwargs)
        normalized.pop('ephemeral', None)
        return normalized

    async def send(self, *args, **kwargs):
        if self.interaction is None:
            kwargs = self._normalize_prefix_response_kwargs(kwargs)
        return await super().send(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        if self.interaction is None:
            kwargs = self._normalize_prefix_response_kwargs(kwargs)
        return await super().reply(*args, **kwargs)

    async def defer(self, *args, **kwargs):
        if self.interaction is None:
            kwargs = self._normalize_prefix_response_kwargs(kwargs)
        return await super().defer(*args, **kwargs)

class AtaraxiaBot(commands.Bot):
    async def get_context(self, message, *, cls=AtaraxiaContext):
        return await super().get_context(message, cls=cls)

bot = AtaraxiaBot(command_prefix=get_prefix, intents=intents, help_command=None)


# Event imports
#-------------------------------------------------------------------
from events import on_member_join
from events import on_member_remove
from events import on_member_update
from events import on_message
from events import on_message_edit
from events import on_raw_message_edit
from events import on_message_delete
from events import on_raw_message_delete
from events import on_raw_reaction_add
from events import on_raw_reaction_remove
from events import on_voice_state_update
from events import on_guild_join
from events import on_interaction
from events import on_ready
from events import on_app_command_completion
#-------------------------------------------------------------------
# Util imports
#-------------------------------------------------------------------
from utils import close
#-------------------------------------------------------------------

# Register event handlers
bot.event(on_ready.on_ready)
bot.event(on_member_join.on_member_join)
bot.event(on_member_remove.on_member_remove)
bot.event(on_member_update.on_member_update)
bot.event(on_message.on_message)
bot.event(on_message_edit.on_message_edit)
bot.event(on_raw_message_edit.on_raw_message_edit)
bot.event(on_message_delete.on_message_delete)
bot.event(on_raw_message_delete.on_raw_message_delete)
bot.event(on_raw_reaction_add.on_raw_reaction_add)
bot.event(on_raw_reaction_remove.on_raw_reaction_remove)
bot.event(on_voice_state_update.on_voice_state_update)
bot.event(on_guild_join.on_guild_join)
bot.event(on_interaction.on_interaction)
bot.event(on_app_command_completion.on_app_command_completion)

# Provide bot reference to event handlers and commands that need it
on_ready.bot = bot
on_member_join.bot = bot
on_member_remove.bot = bot
on_member_update.bot = bot
on_message.bot = bot
on_message_edit.bot = bot
on_message_delete.bot = bot
on_raw_message_edit.bot = bot
on_raw_message_delete.bot = bot
on_raw_reaction_add.bot = bot
on_raw_reaction_remove.bot = bot
on_guild_join.bot = bot
on_raw_reaction_add.bot = bot
on_voice_state_update.bot = bot
close.bot = bot


async def main():
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    flush_interval_raw = os.getenv("COUNTING_CACHE_FLUSH_INTERVAL", "60.0")
    leveling_flush_interval_raw = os.getenv("LEVELING_CACHE_FLUSH_INTERVAL", "60.0")
    leveling_settings_ttl_raw = os.getenv("LEVELING_CACHE_SETTINGS_TTL", "300.0")
    message_flush_interval_raw = os.getenv("MESSAGE_CACHE_FLUSH_INTERVAL", "10.0")

    try:
        counting_flush_interval = max(5.0, float(flush_interval_raw))
    except ValueError:
        logger.warning(
            "Invalid COUNTING_CACHE_FLUSH_INTERVAL=%r, falling back to 60 seconds",
            flush_interval_raw,
        )
        counting_flush_interval = 60.0

    try:
        leveling_flush_interval = max(5.0, float(leveling_flush_interval_raw))
    except ValueError:
        logger.warning(
            "Invalid LEVELING_CACHE_FLUSH_INTERVAL=%r, falling back to 60 seconds",
            leveling_flush_interval_raw,
        )
        leveling_flush_interval = 60.0

    try:
        leveling_settings_ttl = max(10.0, float(leveling_settings_ttl_raw))
    except ValueError:
        logger.warning(
            "Invalid LEVELING_CACHE_SETTINGS_TTL=%r, falling back to 300 seconds",
            leveling_settings_ttl_raw,
        )
        leveling_settings_ttl = 300.0

    try:
        message_flush_interval = max(1.0, float(message_flush_interval_raw))
    except ValueError:
        logger.warning(
            "Invalid MESSAGE_CACHE_FLUSH_INTERVAL=%r, falling back to 10 seconds",
            message_flush_interval_raw,
        )
        message_flush_interval = 10.0

    await db.init_db()  # Initialize the database
    bot.db = db  # Make db accessible to all cogs via self.bot.db
    bot.counting_cache = CountingCacheManager(
        bot,
        cache_path=os.getenv("COUNTING_CACHE_PATH"),
        flush_interval=counting_flush_interval,
    )
    bot.leveling_cache = LevelingCacheManager(
        bot,
        cache_path=os.getenv("LEVELING_CACHE_PATH"),
        flush_interval=leveling_flush_interval,
        settings_ttl=leveling_settings_ttl,
    )
    bot.message_cache = MessageCacheManager(
        bot,
        flush_interval=message_flush_interval,
    )
    logger.info("Counting cache flush interval set to %.1f seconds", counting_flush_interval)
    await bot.counting_cache.start()
    logger.info(
        "Leveling cache flush interval set to %.1f seconds with %.1f second settings TTL",
        leveling_flush_interval,
        leveling_settings_ttl,
    )
    await bot.leveling_cache.start()
    logger.info("Message cache flush interval set to %.1f seconds", message_flush_interval)
    await bot.message_cache.start()
    
    # Load all extensions from cogs directory (recursively)
    # Supports both flat structure (cogs/file.py) and categorized (cogs/category/file.py)
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
    loaded_count = 0
    failed_count = 0
    
    for root, dirs, files in os.walk(cogs_dir):
        # Skip __pycache__ and other private directories
        dirs[:] = [d for d in dirs if not d.startswith('_')]
        
        for filename in files:
            if filename.endswith(".py") and not filename.startswith("_"):
                # Build extension path (e.g., "cogs.moderation.verification" or "cogs.ai")
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, os.path.dirname(__file__))
                ext = rel_path.replace(os.sep, ".")[:-3]  # Remove .py and convert to module path
                
                try:
                    await bot.load_extension(ext)
                    logger.info(f"✅ Loaded extension: {ext}")
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to load {ext}: {e}", exc_info=True)
                    failed_count += 1
    
    logger.info(f"📦 Loaded {loaded_count} cogs ({failed_count} failed)")
    
    close.setup_signal_handlers()

    if not TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    logger.info("Starting bot...")
    
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Fatal error during bot execution: {e}")
    finally:
        # Cleanup on exit
        if hasattr(bot, 'message_cache'):
            await bot.message_cache.close()
            logger.info("Message cache closed.")
        if hasattr(bot, 'leveling_cache'):
            await bot.leveling_cache.close()
            logger.info("Leveling cache closed.")
        if hasattr(bot, 'counting_cache'):
            await bot.counting_cache.close()
            logger.info("Counting cache closed.")
        if hasattr(db, 'close_db'):
            await db.close_db()
            logger.info("Database connection closed.")


if __name__ == "__main__":
    # Acquire process lock before starting
    with ProcessLock():
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass

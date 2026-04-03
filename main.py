# main.py

"""
Ataraxia Discord Bot
Copyright (c) 2025 p1rscher
Licensed under the AGPLv3 License - see LICENSE file for details.
"""

import os
import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
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

bot = commands.Bot(command_prefix="Atx.", intents=intents)


# Event imports
#-------------------------------------------------------------------
from events import on_member_join
from events import on_member_update
from events import on_message
from events import on_message_edit
from events import on_raw_message_edit
from events import on_message_delete
from events import on_raw_message_delete
from events import on_raw_reaction_add
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
bot.event(on_member_update.on_member_update)
bot.event(on_message.on_message)
bot.event(on_message_edit.on_message_edit)
bot.event(on_raw_message_edit.on_raw_message_edit)
bot.event(on_message_delete.on_message_delete)
bot.event(on_raw_message_delete.on_raw_message_delete)
bot.event(on_raw_reaction_add.on_raw_reaction_add)
bot.event(on_voice_state_update.on_voice_state_update)
bot.event(on_guild_join.on_guild_join)
bot.event(on_interaction.on_interaction)
bot.event(on_app_command_completion.on_app_command_completion)

# Provide bot reference to event handlers and commands that need it
on_ready.bot = bot
on_member_join.bot = bot
on_member_update.bot = bot
on_message.bot = bot
on_raw_message_edit.bot = bot
on_raw_message_delete.bot = bot
on_raw_reaction_add.bot = bot
on_guild_join.bot = bot
on_raw_reaction_add.bot = bot
close.bot = bot
# Database reference for events that need it
on_interaction.db = db
on_app_command_completion.db = db


async def main():
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")

    await db.init_db()  # Initialize the database
    
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
    
    # Set db reference in cogs that need it
    if "cogs.bump_reminder" in bot.extensions:
        from cogs import bump_reminder
        bump_reminder.db = db
    if "cogs.admin_stats" in bot.extensions:
        from cogs import admin_stats
        admin_stats.db = db
    if "cogs.counting" in bot.extensions:
        from cogs import counting
        counting.db = db
    if "cogs.level_roles" in bot.extensions:
        from cogs import level_roles
        level_roles.db = db


    close.setup_signal_handlers()

    if not TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    logger.info("Starting bot...")
    
    # Start bot and background tasks concurrently
    async with asyncio.TaskGroup() as tg:
        tg.create_task(bot.start(TOKEN))
        tg.create_task(update_stats_json(bot))
        tg.create_task(grant_voice_xp(bot))
    
    # Cleanup on exit
    if hasattr(db, 'close_db'):
        await db.close_db()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    # Acquire process lock before starting
    with ProcessLock():
        asyncio.run(main())

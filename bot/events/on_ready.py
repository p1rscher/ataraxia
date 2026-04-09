# events/on_ready.py
import discord
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Bot reference to be set from main.py
bot: Optional[discord.Client] = None

async def on_ready():
    logger.info(f"Logged in as {bot.user} (id={bot.user.id})")
    logger.info("on_ready: Starting startup sequence...")

    # Debug: welche app-commands sind aktuell im tree
    logger.debug("Commands in bot.tree:")
    for cmd in bot.tree.get_commands():
        logger.debug(f"- {cmd.name}  ({type(cmd)})  desc={cmd.description}")

    logger.info("on_ready: Syncing commands...")
    for guild in bot.guilds:
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s) to guild {guild.name} (ID: {guild.id})")
        except Exception as e:
            logger.error(f"Failed to sync for {guild.name}: {e}")

    # Import utils for backfill and verification
    from utils import backfill_guild_messages, process_missed_verifications, sync_voice_sessions_on_startup
    
    logger.info("on_ready: Starting backfill...")
    tasks = [backfill_guild_messages(g, backfill_limit=256) for g in bot.guilds]
    await asyncio.gather(*tasks)
    logger.info("Backfill complete")

    logger.info("on_ready: Processing missed verifications...")
    await process_missed_verifications(bot)
    
    logger.info("on_ready: Syncing voice sessions...")
    await sync_voice_sessions_on_startup(bot)

    from core import database_pg as db
    logger.info("on_ready: Backfilling discord_users database...")
    try:
        await db.bulk_upsert_users(bot.users)
        logger.info(f"on_ready: Backfilled {len(bot.users)} global users tightly.")
    except Exception as e:
        logger.error(f"on_ready: Failed to backfill users: {e}")

    logger.info("on_ready: Startup completed - bot is now fully ready!")

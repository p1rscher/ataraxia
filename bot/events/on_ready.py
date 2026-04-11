# events/on_ready.py
import discord
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Bot reference to be set from main.py
bot: Optional[discord.Client] = None

# Flag to ensure background tasks only start once
_tasks_started = False

async def on_ready():
    global _tasks_started
    logger.info(f"Logged in as {bot.user} (id={bot.user.id})")
    logger.info("on_ready: Starting startup sequence...")

    # Debug: welche app-commands sind aktuell im tree
    logger.debug("Commands in bot.tree:")
    for cmd in bot.tree.get_commands():
        logger.debug(f"- {cmd.name}  ({type(cmd)})  desc={cmd.description}")

    async def background_sync_commands(bot_ref):
        logger.info("on_ready: Syncing commands in background...")
        try:
            synced = await bot_ref.tree.sync()
            logger.info(f"Synced {len(synced)} global command(s).")
        except Exception as e:
            logger.error(f"Failed to sync global commands: {e}")

    # Schedule command syncing as a background task
    asyncio.create_task(background_sync_commands(bot))

    # Import utils for backfill and verification
    from utils import backfill_guild_messages, process_missed_verifications, sync_voice_sessions_on_startup, grant_voice_xp, update_stats_json
    
    async def presence_cycle(bot_ref):
        """Cycles the bot's rich presence every 5 minutes."""
        while True:
            try:
                # Status 1: /help
                await bot_ref.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.listening, name="/help")
                )
                await asyncio.sleep(300)
                
                # Status 2: Serving [x] Servers
                server_count = len(bot_ref.guilds)
                await bot_ref.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening, 
                        name=f"Serving {server_count} Servers"
                    )
                )
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in presence cycle: {e}")
                await asyncio.sleep(60) # Wait a bit before retrying if something fails

    # Start background tasks only once
    if not _tasks_started:
        asyncio.create_task(update_stats_json(bot))
        asyncio.create_task(grant_voice_xp(bot))
        asyncio.create_task(presence_cycle(bot))
        _tasks_started = True
        logger.info("on_ready: Started persistent background tasks (stats, voice xp, presence)")

    logger.info("on_ready: Starting backfill...")
    
    # Use a Semaphore to prevent backfilling hundreds of guilds at exactly the same time,
    # which exhausts DB connections and leads to "Max Clients reached" errors from DB hosts.
    sem = asyncio.Semaphore(5)
    
    async def bounded_backfill(guild):
        async with sem:
            await backfill_guild_messages(guild)
            
    tasks = [bounded_backfill(g) for g in bot.guilds]
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

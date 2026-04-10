# events/on_guild_join.py
import discord
import asyncio
import logging
from typing import Optional
from utils import backfill_guild_messages

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_guild_join(guild: discord.Guild):
    """Wird getriggert wenn der Bot einem neuen Server beitritt"""
    logger.info(f"Bot joined new guild: {guild.name} (ID: {guild.id})")

    await asyncio.sleep(20)
    
    # Backfill messages from all channels
    try:
        await backfill_guild_messages(guild, backfill_hours=24*7*4)
        logger.info(f"Backfill completed for {guild.name}")
    except Exception as e:
        logger.error(f"Backfill failed for {guild.name}: {e}")

    # Sync commands to the new guild
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=guild.id))
        logger.info(f"Synced {len(synced)} commands to {guild.name}")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


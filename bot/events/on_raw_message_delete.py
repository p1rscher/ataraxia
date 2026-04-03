# events/on_raw_message_delete.py
import discord
from typing import Optional
import logging

from core import database_pg as db
from utils.embeds import make_delete_embed_from_db

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):

    if payload.cached_message:
        return

    if payload.guild_id is None:
        return

    if payload.cached_message and payload.cached_message.author.bot:
        return


    guild = bot.get_guild(payload.guild_id) if bot else None
    channel_mention = f"<#{payload.channel_id}>"

    # Try to get message from DB
    message_row = None
    try:
        message_row = await db.get_message(payload.message_id)
    except Exception as e:
        logger.error(f"db.get_message failed: {e}")
        return
    
    if not message_row:
        # Silently skip if message not in database (e.g. bot messages, messages before bot joined)
        return
    
    await db.mark_message_deleted(payload.message_id)

    # Create embed
    embed = await make_delete_embed_from_db(message_row, channel_mention)

    # Determine target channel
    target = None
    try:
        LOG_CHANNEL_ID = await db.get_log_channel_id(payload.guild_id)
        if LOG_CHANNEL_ID:
            if guild:
                target = guild.get_channel(int(LOG_CHANNEL_ID))
            if not target and bot:
                target = bot.get_channel(int(LOG_CHANNEL_ID))
            if not target and bot:
                try:
                    target = await bot.fetch_channel(int(LOG_CHANNEL_ID))
                except Exception:
                    target = None

    except Exception as e:
        logger.error(f"db.get_log_channel_id failed: {e}")

    if not target:
        return

    try:
        await target.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send delete log: {e}")

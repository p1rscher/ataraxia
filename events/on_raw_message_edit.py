# events/on_raw_message_edit.py
import discord
import logging
from typing import Optional

from core import database_pg as db
from utils.diff import diff
from utils.embeds import make_edit_embed_from_db

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    if payload.cached_message:
        return

    if payload.guild_id is None:
        return

    guild = bot.get_guild(payload.guild_id) if bot else None



    # Try to get message from DB
    message_row = None
    try:
        message_row = await db.get_message(payload.message_id)
    except Exception as e:
        logger.error(f"db.get_message failed: {e}")
        return
    
    # Skip if message not found (e.g., bot messages, messages before bot joined)
    if not message_row:
        return
    
    # Get old and new content
    old_content = message_row[4] if message_row[4] else ""
    new_content = payload.data.get('content', "")
    
    # Skip if content didn't change
    if old_content == new_content:
        return
    
    diff_text = diff(old_content, new_content)
    

    # Save message to database
    await db.save_message(
        message_id=payload.message_id,
        guild_id=payload.guild_id,
        channel_id=payload.channel_id,
        author_id=message_row[3],
        content=new_content,
    )

    # Create embed
    embed = await make_edit_embed_from_db(message_row, diff_text, bot)


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
        logger.error(f"Error fetching log channel: {e}")

    if not target:
        return

    try:
        await target.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send edit log: {e}")

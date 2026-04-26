# utils/backfill.py
import os
import asyncio
import discord
import logging
from datetime import timedelta
from core import database_pg as db

logger = logging.getLogger(__name__)

# BACKFILL_HOURS can be configured via environment, defaulting to 2
BACKFILL_HOURS = int(os.getenv("BACKFILL_HOURS", "2"))

async def backfill_guild_messages(guild, backfill_hours=BACKFILL_HOURS):
    logger.info(f"Backfilling messages for guild - {guild.name}")
    
    # Collect all channels with message history
    channels_to_backfill = []
    
    # Text Channels
    channels_to_backfill.extend(guild.text_channels)
    
    # Voice channels (also have text chat)
    channels_to_backfill.extend(guild.voice_channels)
    
    # Forum channels (Skip because they do not have a .history attribute)
    # channels_to_backfill.extend([ch for ch in guild.channels if hasattr(ch, 'type') and ch.type == discord.ChannelType.forum])
    
    # Stage channels (can have text chat)
    channels_to_backfill.extend([ch for ch in guild.channels if hasattr(ch, 'type') and ch.type == discord.ChannelType.stage_voice])
    
    after_date = discord.utils.utcnow() - timedelta(hours=backfill_hours)

    for channel in channels_to_backfill:
        # skip if bot has no permission
        perms = channel.permissions_for(guild.me)
        if not (perms.read_message_history and perms.view_channel):
            continue
        try:
            messages_data = []
            async for msg in channel.history(after=after_date, limit=None):
                if msg.author.bot:
                    continue
                
                messages_data.append({
                    'message_id': msg.id,
                    'guild_id': guild.id,
                    'channel_id': channel.id,
                    'author_id': msg.author.id,
                    'content': msg.content,
                    'created_at': msg.created_at,
                    'edited_at': msg.edited_at
                })
                
                # Bulk insert in batches to remain efficient memory-wise
                if len(messages_data) >= 500:
                    await db.bulk_save_messages(messages_data)
                    messages_data = []
                    await asyncio.sleep(0.5)
            
            # Save the remaining messages in the buffer
            if messages_data:
                await db.bulk_save_messages(messages_data)
                
            await asyncio.sleep(0.5)  # pause to avoid rate limits
        except Exception as e:
            # skip on rate limits or protected channels
            logger.warning(f"Skipping channel {channel.name} ({channel.id}) in guild {guild.id}: {e}")
            continue

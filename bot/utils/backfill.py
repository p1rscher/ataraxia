# utils/backfill.py
import asyncio
import discord
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)

BACKFILL_LIMIT = 8192 # amount of messages to backfill per channel

async def backfill_guild_messages(guild, backfill_limit=BACKFILL_LIMIT):
    logger.info(f"Backfilling messages for guild - {guild.name}")
    
    # Collect all channels with message history
    channels_to_backfill = []
    
    # Text Channels
    channels_to_backfill.extend(guild.text_channels)
    
    # Voice channels (also have text chat)
    channels_to_backfill.extend(guild.voice_channels)
    
    # Forum channels (have threads with messages)
    channels_to_backfill.extend([ch for ch in guild.channels if hasattr(ch, 'type') and ch.type == discord.ChannelType.forum])
    
    # Stage channels (can have text chat)
    channels_to_backfill.extend([ch for ch in guild.channels if hasattr(ch, 'type') and ch.type == discord.ChannelType.stage_voice])
    
    for channel in channels_to_backfill:
        # skip if bot has no permission
        perms = channel.permissions_for(guild.me)
        if not (perms.read_message_history and perms.view_channel):
            continue
        try:
            async for msg in channel.history(limit=backfill_limit):
                if msg.author.bot:
                    continue
                await db.save_message(
                    message_id=msg.id,
                    guild_id=guild.id,
                    channel_id=channel.id,
                    author_id=msg.author.id,
                    content=msg.content,
                    created_at=msg.created_at
                )
                await asyncio.sleep(0.2)  # pause to avoid rate limits
        except Exception as e:
            # skip on rate limits or protected channels
            logger.warning(f"Skipping channel {channel.name} ({channel.id}) in guild {guild.id}: {e}")
            continue

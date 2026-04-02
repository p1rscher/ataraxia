# events/on_message_edit.py
import discord
from typing import Optional
import logging

from utils.diff import diff
import core.database_pg as db

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_message_edit(before: discord.Message, after: discord.Message):
    # Ignore bot messages
    if before.author.bot:
        return

    # ignore if content didn't change
    if (before.content or "") == (after.content or ""):
        return

    # Generate diff string
    diff_text = diff(before.content or "", after.content or "")

    # Create embed
    from utils.embeds import make_edit_embed
    embed = await make_edit_embed(before, diff_text)

    # If the message was in DMs, don't log
    if before.guild is None:
        return
    
    target_channel = None
    LOG_CHANNEL_ID = await db.get_log_channel_id(before.guild.id)
    if LOG_CHANNEL_ID is not None:
        try:
            # Ensure it's an int ID
            log_id = int(LOG_CHANNEL_ID)
        except Exception:
            log_id = None
        
        if log_id:
            # Cache
            target_channel = before.guild.get_channel(log_id)

            # API-Fetch as fallback
            if not target_channel:
                try:
                    target_channel = await before.guild.fetch_channel(log_id)
                except Exception:
                    target_channel = None

    # Fallback: Original channel
    if not target_channel:
        target_channel = before.channel

    # Send embed
    try:
        await target_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Error sending edit embed: {e}")
    
       # Save message to database
    await db.save_message(
        message_id=after.id,
        guild_id=after.guild.id if after.guild else 0,
        channel_id=after.channel.id,
        author_id=after.author.id,
        content=after.content,
        edited_at=after.edited_at
    )


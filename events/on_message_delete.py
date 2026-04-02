# events/on_message_delete.py
import discord
import core.database_pg as db
from typing import Optional

from utils.embeds import make_delete_embed


# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_message_delete(message: discord.Message):
    # Ignore bot messages
    if message.author.bot:
        return

    # If the message was in DMs, don't log
    if message.guild is None:
        return

    target_channel = None
    LOG_CHANNEL_ID = await db.get_log_channel_id(message.guild.id)
    if LOG_CHANNEL_ID is not None:
        try:
            # Ensure it's an int ID
            log_id = int(LOG_CHANNEL_ID)
        except Exception:
            log_id = None
        
        if log_id:
            # Cache
            target_channel = message.guild.get_channel(log_id)

            # API-Fetch as fallback
            if not target_channel:
                try:
                    target_channel = await message.guild.fetch_channel(log_id)
                except Exception:
                    target_channel = None
    
    try:
        await db.mark_message_deleted(message.id)
    except Exception as e:
        print("Failed to mark message as deleted:", e)

    if target_channel is None:
        return


    # Create embed
    embed = await make_delete_embed(message, message.channel.mention)

    # Send embed
    try:
        await target_channel.send(embed=embed)
    except Exception as e:
        print("Failed to send delete log message:", e)

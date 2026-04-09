# events/on_message.py
from typing import Optional
import discord
import core.database_pg as db
import datetime
import random
import logging

from utils.xp_calculator import check_level_up

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_message(message: discord.Message):

    # Ignore DMs
    if message.guild is None:
        return

    # Check for Disboard bump response BEFORE ignoring bot messages
    if await bump_response(message):
        return

    # Ignore bot messages for normal message processing
    if message.author.bot:
        return

    # Silently track the user globally with internal cache protection
    await db.upsert_user(message.author)

    # Check XP cooldown before granting XP
    if await db.can_gain_message_xp(message.author.id, message.guild.id):
        # Get customizable XP range for this guild
        xp_min, xp_max = await db.get_message_xp_range(message.guild.id)
        base_xp = random.randint(xp_min, xp_max)
        
        # Calculate total multiplier (user, channel, role, booster)
        total_multiplier = await db.calculate_total_multiplier(message.author, message.channel.id)
        xp = int(base_xp * total_multiplier)
        
        await db.add_xp(message.author.id, message.guild.id, xp)
        await db.update_message_xp_cooldown(message.author.id, message.guild.id)
        
        # Check for level up (can level up multiple times)
        await check_level_up(message.author.id, message.guild.id, bot, message.channel)

        # Passive coin reward for messages (uses same cooldown as XP)
        try:
            eco_settings = await db.get_economy_settings(message.guild.id)
            coin_amount = random.randint(eco_settings['message_coins_min'], eco_settings['message_coins_max'])
            if coin_amount > 0:
                await db.add_coins(message.author.id, message.guild.id, coin_amount)
        except Exception as e:
            logger.error(f"Failed to grant message coins: {e}")

   # Save message to database
    await db.save_message(
        message_id=message.id,
        guild_id=message.guild.id if message.guild else 0,
        channel_id=message.channel.id,
        author_id=message.author.id,
        content=message.content,
        created_at=message.created_at
    )
    
    # Process prefix commands (required for @commands.command decorators)
    await bot.process_commands(message)


async def bump_response(message: discord.Message):
    # Check for Disboard bump response BEFORE ignoring bot messages
    if not (message.author.id == 302050872383242240):  # Disboard Bot ID
        return False
    
    # Check if it's a bump success message (has embeds and specific content)
    if not (message.embeds and len(message.embeds) > 0):
        return True
    
    embed = message.embeds[0]

    # Disboard sends an embed with description containing "Bump done"
    if not (embed.description and ":thumbsup:" in embed.description):
        return True
        
    # Get bump settings
    settings = await db.get_bump_settings(message.guild.id)
    if not (settings and settings['enabled']):
        return True
    
    # Save bump time (this will also reset reminded_id to NULL)
    bump_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    await db.update_last_bump(message.guild.id, bump_time)
    logger.info(f"Bump detected in guild {message.guild.id}")

    # Delete the previous reminder message if it exists
    if settings['reminder_id'] is not None:
        try:
            channel = message.guild.get_channel(settings['reminder_channel_id'])
            if channel:
                msg = await channel.fetch_message(settings['reminder_id'])
                await msg.delete()
                logger.debug(f"Deleted old reminder message {settings['reminder_id']} in guild {message.guild.id}")
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"Error deleting reminder message: {e}")

    return True

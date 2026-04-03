# utils/voice_xp.py
import asyncio
import random
import logging
from datetime import datetime, timezone
from core import database_pg as db
from utils.xp_calculator import check_level_up

logger = logging.getLogger(__name__)

async def grant_voice_xp(bot):
    """Grant XP to users in voice channels based on guild-specific intervals"""
    logger.info("grant_voice_xp: Waiting for bot to be ready...")
    while not bot.is_ready():
        await asyncio.sleep(1)
    logger.info("grant_voice_xp: Bot ready, starting XP grants")
    
    while not bot.is_closed():
        try:
            # Get all voice sessions that need XP (check every 10 seconds for sessions ready for XP)
            sessions = await db.get_all_active_voice_sessions()
            
            for session in sessions:
                user_id = session['user_id']
                guild_id = session['guild_id']
                channel_id = session['channel_id']
                
                # Get guild and member
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue
                
                member = guild.get_member(user_id)
                if not member:
                    # User no longer in guild, clean up session
                    await db.end_voice_session(user_id, guild_id)
                    continue
                
                # Check if user is still in voice channel
                voice_state = member.voice
                if not voice_state or not voice_state.channel:
                    # User left, clean up session
                    await db.end_voice_session(user_id, guild_id)
                    continue
                
                # Get guild-specific voice XP requirements
                requirements = await db.get_voice_xp_requirements(guild_id)
                
                # Check AFK requirement
                if requirements['require_non_afk'] and voice_state.afk:
                    continue
                
                # Check deaf requirement
                if requirements['require_non_deaf'] and (voice_state.self_deaf or voice_state.deaf):
                    continue
                
                # Check muted requirement
                if requirements['require_non_muted'] and (voice_state.self_mute or voice_state.mute):
                    continue
                
                # Check if user is alone in channel requirement
                if requirements['require_others_in_channel']:
                    # Count non-bot members in channel
                    non_bot_members = [m for m in voice_state.channel.members if not m.bot]
                    if len(non_bot_members) <= 1:
                        continue

                # Check if enough time has passed based on guild settings
                voice_interval = await db.get_voice_xp_interval(guild_id)
                last_grant = session['last_xp_grant']
                if last_grant.tzinfo is None:
                    last_grant = last_grant.replace(tzinfo=timezone.utc)
                time_since = (datetime.now(timezone.utc) - last_grant).total_seconds()
                
                if time_since < voice_interval:
                    continue

                # Grant XP with customizable range and multipliers
                xp_min, xp_max = await db.get_voice_xp_range(guild_id)
                base_xp = random.randint(xp_min, xp_max)
                
                # Calculate total multiplier (user, channel, role, booster)
                total_multiplier = await db.calculate_total_multiplier(member, channel_id)
                xp = int(base_xp * total_multiplier)
                
                await db.add_xp(user_id, guild_id, xp)
                await db.update_voice_xp_grant(user_id, guild_id)
                
                logger.debug(f"Granted {xp} voice XP to user {user_id} in guild {guild_id}")
                
                # Check for level up
                # If level log channel is configured, it will be used automatically
                # Otherwise, try to find a fallback channel for voice XP level-ups
                fallback_channel = guild.system_channel
                if not fallback_channel:
                    # Try to find first text channel bot has access to
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            fallback_channel = channel
                            break
                
                levels_gained = await check_level_up(user_id, guild_id, bot, fallback_channel)
                if levels_gained > 0:
                    logger.info(f"User {user_id} gained {levels_gained} level(s) from voice XP in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to grant voice XP: {e}", exc_info=True)
        
        # Check every 10 seconds
        await asyncio.sleep(10)

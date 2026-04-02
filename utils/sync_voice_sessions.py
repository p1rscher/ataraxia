# utils/sync_voice_sessions.py

"""
Ataraxia Discord Bot
Copyright (c) 2025 p1rscher
Licensed under the AGPLv3 License - see LICENSE file for details.
"""

import logging
from core import database_pg as db

logger = logging.getLogger(__name__)

async def sync_voice_sessions_on_startup(bot):
    """
    Synchronize voice sessions when bot starts.
    This ensures users already in voice channels get their sessions created.
    
    Args:
        bot: The Discord bot instance
    """
    logger.info("Syncing voice sessions on startup...")
    sessions_created = 0
    sessions_cleaned = 0
    
    # Get all currently active sessions from database
    active_sessions = await db.get_all_active_voice_sessions(0)
    active_session_keys = {(s['user_id'], s['guild_id']) for s in active_sessions}
    
    for guild in bot.guilds:
        # Get voice XP requirements for this guild
        requirements = await db.get_voice_xp_requirements(guild.id)
        
        # Track who SHOULD have sessions
        should_have_session = set()
        
        for channel in guild.voice_channels:
            # Skip AFK channels
            if guild.afk_channel and channel.id == guild.afk_channel.id:
                continue
            
            # Count non-bot members
            non_bot_members = [m for m in channel.members if not m.bot]
            
            # Check if this channel has enough people for XP (if requirement is enabled)
            if requirements['require_others_in_channel'] and len(non_bot_members) <= 1:
                continue
            
            # Create sessions for eligible users
            for member in non_bot_members:
                should_have_session.add((member.id, guild.id))
                
                # Check if they already have a session
                if (member.id, guild.id) not in active_session_keys:
                    try:
                        await db.start_voice_session(member.id, guild.id, channel.id)
                        sessions_created += 1
                        logger.debug(f"Created voice session for {member} in {channel.name}")
                    except Exception as e:
                        logger.error(f"Failed to create voice session for {member}: {e}")
        
        # Clean up sessions for users who are no longer in voice or shouldn't have sessions
        for session in active_sessions:
            if session['guild_id'] == guild.id:
                user_id = session['user_id']
                
                # If user shouldn't have a session, remove it
                if (user_id, guild.id) not in should_have_session:
                    try:
                        await db.end_voice_session(user_id, guild.id)
                        sessions_cleaned += 1
                        logger.debug(f"Cleaned up stale voice session for user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to clean up voice session: {e}")
    
    logger.info(f"Voice session sync complete: {sessions_created} created, {sessions_cleaned} cleaned")

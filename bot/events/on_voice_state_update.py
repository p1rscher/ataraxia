# events/on_voice_state_update.py
import discord
import logging
from core import database_pg as db
from datetime import datetime

logger = logging.getLogger(__name__)

async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Handle temporary voice channel creation/deletion, voice XP tracking, and voice logs"""
    
    # ==================== VOICE LOGGING ====================
    
    # Get voice log channel
    voice_log_channel_id = await db.get_voice_log_channel_id(member.guild.id)
    if voice_log_channel_id:
        voice_log_channel = member.guild.get_channel(voice_log_channel_id)
        
        if voice_log_channel:
            embed = None
            
            # User joined a voice channel
            if after.channel and not before.channel:
                embed = discord.Embed(
                    title="🔊 Voice Channel Joined",
                    description=f"{member.mention} joined {after.channel.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
                embed.add_field(name="Channel", value=after.channel.name, inline=True)
                
            # User left a voice channel
            elif before.channel and not after.channel:
                embed = discord.Embed(
                    title="🔇 Voice Channel Left",
                    description=f"{member.mention} left {before.channel.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
                embed.add_field(name="Channel", value=before.channel.name, inline=True)
                
            # User switched voice channels
            elif before.channel and after.channel and before.channel != after.channel:
                embed = discord.Embed(
                    title="↔️ Voice Channel Switched",
                    description=f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
                embed.add_field(name="From", value=before.channel.name, inline=True)
                embed.add_field(name="To", value=after.channel.name, inline=True)
            
            # Send the log embed
            if embed:
                try:
                    await voice_log_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send voice log: {e}", exc_info=True)
    
    # ==================== VOICE XP TRACKING ====================
    
    # User left a voice channel (end session first if switching channels)
    if before.channel and (not after.channel or after.channel != before.channel):
        # End voice session tracking for the leaving user
        try:
            await db.end_voice_session(member.id, member.guild.id)
            logger.info(f"🔴 Ended voice session for {member} (left {before.channel.name})")
        except Exception as e:
            logger.error(f"Failed to end voice session: {e}", exc_info=True)
        
        # IMPORTANT: If this leaves only one non-bot person in the channel, end their session too
        # (Only if require_others_in_channel is enabled)
        if before.channel:
            requirements = await db.get_voice_xp_requirements(member.guild.id)
            non_bot_members = [m for m in before.channel.members if not m.bot]
            
            if requirements['require_others_in_channel'] and len(non_bot_members) == 1:
                for other_member in non_bot_members:
                    try:
                        await db.end_voice_session(other_member.id, member.guild.id)
                        logger.info(f"🔴 Ended voice session for now-alone user {other_member}")
                    except Exception as e:
                        logger.error(f"Failed to end voice session for remaining member: {e}", exc_info=True)
    
    # User joined a voice channel (create session after ending old one)
    if after.channel and after.channel != before.channel:
        # Don't track AFK channels
        if not (member.guild.afk_channel and after.channel.id == member.guild.afk_channel.id):
            logger.info(f"Voice join detected: {member} joined {after.channel.name}")
            # Get guild-specific voice XP requirements
            requirements = await db.get_voice_xp_requirements(member.guild.id)
            logger.info(f"Requirements for guild {member.guild.id}: {requirements}")
            
            # Count non-bot members in the channel
            non_bot_members = [m for m in after.channel.members if not m.bot]
            logger.info(f"Non-bot members in channel: {len(non_bot_members)} ({[m.name for m in non_bot_members]})")
            
            # Check if this user should get a session based on requirements
            should_start_session = True
            
            # Check if requirement is to have others in channel
            if requirements['require_others_in_channel'] and len(non_bot_members) <= 1:
                should_start_session = False
            
            # Start voice session tracking for the joining user (if requirements met)
            if should_start_session:
                try:
                    await db.start_voice_session(member.id, member.guild.id, after.channel.id)
                    logger.info(f"✅ Started voice session for {member} in {after.channel.name}")
                except Exception as e:
                    logger.error(f"Failed to start voice session: {e}", exc_info=True)
            else:
                logger.info(f"❌ Did NOT start session for {member} - requirements not met (alone in channel)")
            
            # IMPORTANT: If this is the second person joining, also start session for the first user
            # This handles the case where someone was alone and now has company
            if requirements['require_others_in_channel'] and len(non_bot_members) == 2:
                for other_member in non_bot_members:
                    if other_member.id != member.id:
                        try:
                            # Check if they already have an active session
                            existing_session = await db.get_voice_session(other_member.id, member.guild.id)
                            if not existing_session:
                                await db.start_voice_session(other_member.id, member.guild.id, after.channel.id)
                                logger.info(f"✅ Started voice session for previously alone user {other_member}")
                        except Exception as e:
                            logger.error(f"Failed to start voice session for existing member: {e}", exc_info=True)
    
    # ==================== TEMP VOICE CHANNELS ====================
    
    # User joined a voice channel
    if after.channel and after.channel != before.channel:
        # Check if this channel is a creator channel
        creator_info = await db.get_temp_voice_creator_info(after.channel.id)
        
        if creator_info:
            guild_id, category_id = creator_info
            
            # Determine the category
            if category_id:
                category = member.guild.get_channel(category_id)
            else:
                category = after.channel.category
            
            try:
                temp_channel = await member.guild.create_voice_channel(
                    name=f"{member.display_name}'s Channel",
                    category=category,
                    reason="Temporary voice channel"
                )
                
                await member.move_to(temp_channel)
                await db.add_temp_voice_channel(temp_channel.id, member.guild.id, member.id)
                
            except discord.Forbidden:
                logger.error(f"Keine Berechtigung, Voice-Channel in {member.guild.name} zu erstellen")
            except Exception as e:
                logger.error(f"Fehler beim Erstellen des Temp-Voice-Channels: {e}", exc_info=True)
    
    # User left a voice channel
    if before.channel and before.channel != after.channel:
        # Check if it's a temporary channel
        is_temp = await db.is_temp_voice_channel(before.channel.id)
        
        if is_temp and len(before.channel.members) == 0:
            # Channel is empty, delete it
            try:
                await before.channel.delete(reason="Temporary voice channel empty")
                await db.remove_temp_voice_channel(before.channel.id)
            except discord.Forbidden:
                logger.error(f"Missing permissions to delete channel {before.channel.id}")
            except discord.NotFound:
                # Channel already deleted
                await db.remove_temp_voice_channel(before.channel.id)
            except Exception as e:
                logger.error(f"Error deleting temp voice channel: {e}", exc_info=True)

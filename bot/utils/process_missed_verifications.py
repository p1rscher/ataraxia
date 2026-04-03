# utils/process_missed_verifications.py
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)

async def process_missed_verifications(bot):
    """Process missed verification reactions across all guilds."""
    
    for guild in bot.guilds:
        # Get verification settings for this guild
        verification_data = await db.get_verification(guild.id)
        if not verification_data:
            continue
            
        message_id, channel_id, role_id = verification_data

        # Get channel and role
        channel = guild.get_channel(channel_id)
        if not channel:
            logger.warning(f"[Verification] Channel {channel_id} not found in guild {guild.name}, removing from DB")
            await db.remove_verification(guild.id)
            continue
            
        role = guild.get_role(role_id)
        if not role:
            logger.warning(f"[Verification] Role {role_id} not found in guild {guild.name}, removing from DB")
            await db.remove_verification(guild.id)
            continue

        # Try to fetch the message
        try:
            message = await channel.fetch_message(message_id)
        except Exception as e:
            logger.warning(f"[Verification] Message {message_id} not found in {guild.name} (deleted by admin?), removing from DB")
            await db.remove_verification(guild.id)
            continue

        # Get all ✅ reactions
        for reaction in message.reactions:
            if str(reaction.emoji) != "✅":
                continue

            # Check all users with this reaction
            async for user in reaction.users():
                # Ignore bot itself
                if user.id == bot.user.id:
                    continue

                # Try to fetch member
                member = guild.get_member(user.id)
                if not member:
                    continue

                # If member doesn't have role, assign it
                if role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Verification System (missed reaction)")
                        logger.info(f"Verified missed user {member} in {guild.name}")
                    except Exception as e:
                        logger.error(f"Failed to add role to {member} in {guild.name}: {e}")
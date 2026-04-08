# events/on_raw_reaction_add.py
import discord
import logging
from typing import Optional
from core import database_pg as db

# set bot reference from main.py
bot: Optional[discord.Client] = None
logger = logging.getLogger(__name__)

async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if bot is None or bot.user is None:
        return

    # ignore bot reactions
    if payload.user_id == bot.user.id:
        return

    if not payload.guild_id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

    emoji = str(payload.emoji)

    # Check generic reaction role panels first
    reaction_role_entry = await db.get_reaction_role_entry(payload.message_id, emoji)
    if reaction_role_entry:
        role = guild.get_role(reaction_role_entry['role_id'])
        if role:
            try:
                await member.add_roles(role, reason="Reaction role panel")
            except Exception as exc:
                logger.error(f"Failed to add reaction role {role.id} to {member}: {exc}")

    # Check if this is the verification message
    if emoji != "✅":
        return

    verification_data = await db.get_verification(payload.guild_id)
    if not verification_data:
        return
        
    message_id, channel_id, role_id = verification_data
    
    if payload.message_id != message_id or payload.channel_id != channel_id:
        return
        
    # Assign role to the user
    role = guild.get_role(role_id)
    if not role:
        logger.warning(f"Verification role {role_id} not found in guild {guild.name}")
        return

    try:
        await member.add_roles(role, reason="Verification System")
        logger.info(f"Verified user {member} in {guild.name}")
    except Exception as e:
        logger.error(f"Failed to add role to {member} in {guild.name}: {e}")

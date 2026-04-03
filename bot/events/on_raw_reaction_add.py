# events/on_raw_reaction_add.py
import discord
from typing import Optional
from core import database_pg as db

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # ignore bot reactions
    if payload.user_id == bot.user.id:
        return

    # only in guilds and only for ✅ emoji
    if not payload.guild_id or str(payload.emoji) != "✅":
        return
        
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    # Check if this is the verification message
    verification_data = await db.get_verification(payload.guild_id)
    if not verification_data:
        return
        
    message_id, channel_id, role_id = verification_data
    
    if payload.message_id != message_id or payload.channel_id != channel_id:
        return
        
    # Assign role to the user
    role = guild.get_role(role_id)
    if not role:
        print(f"Verification role {role_id} not found in guild {guild.name}")
        return
        
    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except:
            return
            
    try:
        await member.add_roles(role, reason="Verification System")
        print(f"Verified user {member} in {guild.name}")
    except Exception as e:
        print(f"Failed to add role to {member} in {guild.name}: {e}")

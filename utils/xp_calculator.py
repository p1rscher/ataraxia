# utils/xp_calculator.py
import discord
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)

async def calculate_xp_needed(level: int) -> int:
    """Calculate the XP needed for the given level"""
    return 15 * (level ** 2) + 60 * level + 25

async def check_level_up(user_id: int, guild_id: int, bot: discord.Client, fallback_channel: discord.TextChannel = None):
    """
    Check if a user leveled up and handle it.
    Can level up multiple times if they have enough XP.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        bot: Discord bot instance
        fallback_channel: Channel to send notification if no level log channel is configured
    
    Returns the number of levels gained.
    """
    level_data = await db.get_level(user_id, guild_id)
    if not level_data:
        return 0
    
    current_level = level_data['level']
    current_xp = level_data['xp']
    levels_gained = 0
    
    # Keep checking for level ups until XP is not enough
    while True:
        new_level = current_level + 1
        xp_needed = await calculate_xp_needed(new_level)
        
        if current_xp >= xp_needed:
            # Level up!
            await db.set_level(user_id, guild_id, new_level)
            current_level = new_level
            levels_gained += 1
            logger.info(f"User {user_id} leveled up to {new_level} in guild {guild_id}")
        else:
            # No more level ups
            break
    
    # Send notification if levels were gained
    if levels_gained > 0:
        # Try to get configured level log channel first
        level_log_channel_id = await db.get_level_log_channel_id(guild_id)
        notification_channel = None
        
        guild = bot.get_guild(guild_id)
        if not guild:
            return levels_gained
        
        member = guild.get_member(user_id)
        if not member:
            return levels_gained
        
        # Handle level roles - remove old ones and add new one
        await handle_level_roles(guild, member, current_level)
        
        if level_log_channel_id:
            # Use configured level log channel
            notification_channel = guild.get_channel(level_log_channel_id)
        else:
            # Use fallback channel (e.g., where message was sent)
            notification_channel = fallback_channel
        
        # Send embed if we have a channel
        if notification_channel:
            try:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{member.mention} has reached **Level {current_level}**!",
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Current XP", value=f"{current_xp:,}", inline=True)
                embed.add_field(name="Next Level", value=f"{await calculate_xp_needed(current_level + 1):,} XP", inline=True)
                
                if levels_gained > 1:
                    embed.set_footer(text=f"🚀 {levels_gained} levels gained!")
                
                # Check if user got a new role
                role_id = await db.get_level_role(guild_id, current_level)
                if role_id:
                    role = guild.get_role(role_id)
                    if role:
                        embed.add_field(name="🎁 Role Unlocked", value=role.mention, inline=False)
                
                await notification_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send level up notification: {e}", exc_info=True)
    
    return levels_gained

async def handle_level_roles(guild: discord.Guild, member: discord.Member, new_level: int):
    """
    Handle level role assignment and removal.
    Removes all other level roles and adds the appropriate role for the new level.
    """
    try:
        # Get all configured level roles for this guild
        all_level_roles = await db.get_all_level_roles(guild.id)
        
        if not all_level_roles:
            return  # No level roles configured
        
        # Find which role the user should have (highest level they've reached)
        role_to_add = None
        highest_reached_level = 0
        
        for level, role_id in all_level_roles:
            if level <= new_level and level > highest_reached_level:
                highest_reached_level = level
                role_to_add = guild.get_role(role_id)
        
        # Get all level role IDs to check which ones to remove
        level_role_ids = [role_id for _, role_id in all_level_roles]
        
        # Remove all level roles except the one they should have
        roles_to_remove = []
        for role_id in level_role_ids:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                if role != role_to_add:
                    roles_to_remove.append(role)
        
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Level role update")
            logger.info(f"Removed {len(roles_to_remove)} old level roles from {member} in {guild}")
        
        # Add the new role if they should have one and don't already
        if role_to_add and role_to_add not in member.roles:
            await member.add_roles(role_to_add, reason=f"Reached Level {highest_reached_level}")
            logger.info(f"Added level role {role_to_add.name} to {member} in {guild}")
            
    except Exception as e:
        logger.error(f"Error handling level roles for {member} in {guild}: {e}", exc_info=True)
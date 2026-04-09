import discord
import logging
from typing import Optional
from core import database_pg as db

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_member_update(before: discord.Member, after: discord.Member):
    """Auto-assign parent roles when child roles are added and track global user changes."""
    
    # Track username or global_name changes globally
    if before.name != after.name or before.global_name != after.global_name:
        await db.upsert_user(after, force=True)
    
    # Check if roles changed
    if before.roles == after.roles:
        return
    
    guild = after.guild
    member_role_ids = {role.id for role in after.roles}
    
    # Get all parent role configurations for this guild
    parent_configs = await db.get_all_parent_roles(guild.id)
    
    if not parent_configs:
        return
    
    roles_to_add = []
    
    for config in parent_configs:
        parent_role_id = config['parent_role_id']
        child_role_ids = config['child_role_ids'] if config['child_role_ids'] else []
        
        # Check if member has any child role
        has_child = any(child_id in member_role_ids for child_id in child_role_ids)
        
        # Check if member already has parent role
        has_parent = parent_role_id in member_role_ids
        
        # If has child but missing parent, add parent
        if has_child and not has_parent:
            parent_role = guild.get_role(parent_role_id)
            if parent_role:
                roles_to_add.append(parent_role)
    
    if roles_to_add:
        try:
            await after.add_roles(*roles_to_add, reason="Auto-assign parent roles")
            role_names = [r.name for r in roles_to_add]
            logger.info(f"Assigned parent roles {role_names} to {after} in guild {guild.id}")
        except Exception as e:
            logger.error(f"Failed to assign parent roles to {after} in guild {guild.id}: {e}")

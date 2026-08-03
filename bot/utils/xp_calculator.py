# utils/xp_calculator.py
import discord
import logging
from core import database_pg as db
from utils.embeds import (
    get_embed_color,
    has_time_placeholder,
    normalize_embed_fields,
    process_member_text,
    set_embed_footer,
)

logger = logging.getLogger(__name__)

async def calculate_xp_needed(level: int) -> int:
    """Calculate the XP needed for the given level"""
    return int((40*(level ** 2) + 60*level) * 1.01**level)

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
    level_data = await bot.leveling_cache.get_level(user_id, guild_id)
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
            await bot.leveling_cache.set_level(user_id, guild_id, new_level)
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
        
        if level_log_channel_id == 0:
            # Explicitly disabled
            notification_channel = None
        elif level_log_channel_id:
            # Use configured level log channel
            notification_channel = guild.get_channel(level_log_channel_id)
        else:
            # Use fallback channel (e.g., where message was sent)
            notification_channel = fallback_channel
        
        # Send embed if we have a channel
        if notification_channel:
            try:
                role_id = await db.get_level_role(guild_id, current_level)
                role_mention = None
                if role_id:
                    role = guild.get_role(role_id)
                    if role:
                        role_mention = role.mention

                config = await db.get_level_up_embed_config(guild_id)
                if not config:
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"{member.mention} has reached **Level {current_level}**!",
                        color=await get_embed_color(guild_id, 'level_up_notification', 'color_level_up')
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="Current XP", value=f"{current_xp:,}", inline=True)
                    embed.add_field(name="Next Level", value=f"{await calculate_xp_needed(current_level + 1):,} XP", inline=True)

                    if levels_gained > 1:
                        embed.set_footer(text=f"🚀 {levels_gained} levels gained!")

                    if role_mention:
                        embed.add_field(name="🎁 Role Unlocked", value=role_mention, inline=False)

                    await notification_channel.send(embed=embed)
                else:
                    now = discord.utils.utcnow()
                    next_level_xp = await calculate_xp_needed(current_level + 1)
                    extra_values = {
                        'event': 'level_up',
                        'level': str(current_level),
                        'levels_gained': str(levels_gained),
                        'current_xp': f"{current_xp:,}",
                        'next_level_xp': f"{next_level_xp:,}",
                        'role_unlocked': role_mention or '',
                    }

                    def render(value, *, footer=False):
                        if not value:
                            return None
                        return process_member_text(
                            value,
                            member,
                            event_time=now,
                            time_value="" if footer else None,
                            extra_values=extra_values,
                        ) or None

                    fields = normalize_embed_fields(config.get('fields'))
                    embed_enabled = bool(config.get('embed_enabled', True))
                    embed_values = [
                        config.get('title'),
                        config.get('description'),
                        config.get('author_name'),
                        config.get('author_icon'),
                        config.get('thumbnail'),
                        config.get('image'),
                        config.get('footer_text'),
                        config.get('footer_icon'),
                    ]
                    timestamp_enabled = bool(config.get('timestamp_enabled', False))
                    should_build_embed = embed_enabled and any([
                        config.get('title'),
                        config.get('description'),
                        config.get('author_name'),
                        config.get('thumbnail'),
                        config.get('image'),
                        config.get('footer_text'),
                        config.get('footer_icon'),
                        fields,
                    ])

                    embed = None
                    if should_build_embed:
                        embed = discord.Embed(
                            title=render(config.get('title')),
                            description=render(config.get('description')),
                            color=await get_embed_color(guild_id, 'level_up_notification', 'color_level_up'),
                            timestamp=(
                                now if (timestamp_enabled or has_time_placeholder(*embed_values)) else None
                            ),
                        )
                        if config.get('author_name'):
                            embed.set_author(
                                name=render(config.get('author_name')) or ' ',
                                icon_url=render(config.get('author_icon')),
                            )
                        if config.get('thumbnail'):
                            embed.set_thumbnail(url=render(config.get('thumbnail')))
                        if config.get('image'):
                            embed.set_image(url=render(config.get('image')))
                        set_embed_footer(
                            embed,
                            text=render(config.get('footer_text'), footer=True),
                            icon_url=render(config.get('footer_icon')),
                        )
                        for field in fields[:25]:
                            if not isinstance(field, dict) or not field.get('name'):
                                continue
                            embed.add_field(
                                name=render(field.get('name')) or 'Field',
                                value=(render(field.get('value')) or '-')[:1024],
                                inline=bool(field.get('inline', False)),
                            )

                    content = render(config.get('message'))
                    if embed is None and not content:
                        if embed_enabled:
                            embed = discord.Embed(
                                title="🎉 Level Up!",
                                description=f"{member.mention} has reached **Level {current_level}**!",
                                color=await get_embed_color(guild_id, 'level_up_notification', 'color_level_up')
                            )
                    if embed is not None or content:
                        await notification_channel.send(content=content, embed=embed)
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
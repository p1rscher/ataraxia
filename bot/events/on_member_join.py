import discord
import logging
from typing import Optional
from core import database_pg as db
from utils.embeds import (
    get_embed_color,
    has_time_placeholder,
    process_member_text,
    send_member_traffic_embed,
)

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_member_join(member: discord.Member):
    """Handle new member joining - assign autoroles and send welcome message"""
    
    # Globally track the user
    await db.upsert_user(member, force=True)
    
    # Get autorole settings for this guild
    settings = await db.get_autorole_settings(member.guild.id)
    
    if settings and settings['enabled']:
        if member.bot:
            role_ids = settings.get('bot_role_ids') or []
        else:
            role_ids = settings.get('user_role_ids') or []
            
        roles = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]
        
        if roles:
            try:
                await member.add_roles(*roles, reason="Autorole")
                role_names = [r.name for r in roles]
                logger.info(f"Assigned autoroles {role_names} to {'bot' if member.bot else 'user'} {member} in guild {member.guild.id}")
            except Exception as e:
                logger.error(f"Failed to assign autoroles to {member} in guild {member.guild.id}: {e}")

    # Send welcome message if configured
    welcome = await db.get_welcome_message(member.guild.id)
    if welcome and welcome.get('channel_id'):
        channel = member.guild.get_channel(welcome['channel_id'])
        if channel:
            try:
                event_time = discord.utils.utcnow()
                process_text = lambda value: process_member_text(
                    value,
                    member,
                    event_time=event_time,
                )
                process_embed_text = lambda value: process_member_text(
                    value,
                    member,
                    event_time=event_time,
                )
                process_footer_text = lambda value: process_member_text(
                    value,
                    member,
                    event_time=event_time,
                    time_value="",
                )
                content = process_text(welcome.get('message'))
                
                embed = None
                if any(welcome.get(k) for k in ['embed_title', 'embed_description', 'embed_image', 'embed_thumbnail', 'embed_author_name', 'embed_footer_text']):
                    embed_values = [
                        welcome.get('embed_title'),
                        welcome.get('embed_description'),
                        welcome.get('embed_author_name'),
                        welcome.get('embed_author_icon'),
                        welcome.get('embed_thumbnail'),
                        welcome.get('embed_image'),
                        welcome.get('embed_footer_text'),
                        welcome.get('embed_footer_icon'),
                    ]
                    embed = discord.Embed(
                        title=process_embed_text(welcome.get('embed_title')) or None,
                        description=process_embed_text(welcome.get('embed_description')) or None,
                        color=await get_embed_color(member.guild.id, 'welcome_message', 'color_welcome'),
                        timestamp=event_time if has_time_placeholder(*embed_values) else None,
                    )
                    
                    if welcome.get('embed_author_name'):
                        icon = process_embed_text(welcome.get('embed_author_icon')) or None
                        embed.set_author(name=process_embed_text(welcome.get('embed_author_name')), icon_url=icon)
                        
                    if welcome.get('embed_thumbnail'):
                        embed.set_thumbnail(url=process_embed_text(welcome.get('embed_thumbnail')))
                        
                    if welcome.get('embed_image'):
                        embed.set_image(url=process_embed_text(welcome.get('embed_image')))
                        
                    if welcome.get('embed_footer_text'):
                        icon = process_footer_text(welcome.get('embed_footer_icon')) or None
                        embed.set_footer(text=process_footer_text(welcome.get('embed_footer_text')), icon_url=icon)

                if not embed and not content:
                    pass # Nothing to send
                else:
                    await channel.send(content=content if content else None, embed=embed)
                    logger.info(f"Sent welcome message for {member} in guild {member.guild.id}")
            except Exception as e:
                logger.error(f"Failed to send welcome message for {member} in guild {member.guild.id}: {e}")

    try:
        await send_member_traffic_embed(member, 'join')
    except Exception as e:
        logger.error(f"Failed to send traffic join log for {member} in guild {member.guild.id}: {e}")

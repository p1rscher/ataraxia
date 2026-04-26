import discord
import logging
from typing import Optional
from core import database_pg as db
from utils.embeds import get_guild_color

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
                def process_text(txt):
                    if not txt: return ""
                    txt = txt.replace("{user}", member.mention)
                    txt = txt.replace("{user.name}", str(member))
                    txt = txt.replace("{user.avatar}", member.display_avatar.url)
                    txt = txt.replace("{server}", member.guild.name)
                    txt = txt.replace("{server.icon}", member.guild.icon.url if member.guild.icon else "")
                    txt = txt.replace("{member_count}", str(member.guild.member_count))
                    return txt

                content = process_text(welcome.get('message'))
                
                embed = None
                if any(welcome.get(k) for k in ['embed_title', 'embed_description', 'embed_image', 'embed_thumbnail', 'embed_author_name', 'embed_footer_text']):
                    embed = discord.Embed(
                        title=process_text(welcome.get('embed_title')) or None,
                        description=process_text(welcome.get('embed_description')) or None,
                        color=await get_guild_color(member.guild.id, 'color_welcome')
                    )
                    
                    if welcome.get('embed_author_name'):
                        icon = process_text(welcome.get('embed_author_icon')) or None
                        embed.set_author(name=process_text(welcome.get('embed_author_name')), icon_url=icon)
                        
                    if welcome.get('embed_thumbnail'):
                        embed.set_thumbnail(url=process_text(welcome.get('embed_thumbnail')))
                        
                    if welcome.get('embed_image'):
                        embed.set_image(url=process_text(welcome.get('embed_image')))
                        
                    if welcome.get('embed_footer_text'):
                        icon = process_text(welcome.get('embed_footer_icon')) or None
                        embed.set_footer(text=process_text(welcome.get('embed_footer_text')), icon_url=icon)

                if not embed and not content:
                    pass # Nothing to send
                else:
                    await channel.send(content=content if content else None, embed=embed)
                    logger.info(f"Sent welcome message for {member} in guild {member.guild.id}")
            except Exception as e:
                logger.error(f"Failed to send welcome message for {member} in guild {member.guild.id}: {e}")

    # Send user traffic log if configured
    traffic_channel_id = await db.get_traffic_log_channel_id(member.guild.id)
    if traffic_channel_id:
        traffic_channel = member.guild.get_channel(traffic_channel_id)
        if traffic_channel and isinstance(traffic_channel, discord.TextChannel):
            try:
                created_ts = int(member.created_at.timestamp())
                color = await get_guild_color(member.guild.id)

                embed = discord.Embed(
                    title=f"{member.display_name} joined the server",
                    color=color,
                )
                embed.add_field(
                    name="User",
                    value=member.mention,
                    inline=True,
                )
                embed.add_field(
                    name="Account creation",
                    value=f"<t:{created_ts}:f> (<t:{created_ts}:R>)",
                    inline=True,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(
                    text=f"{member.guild.name} • {member.guild.member_count} members",
                    icon_url=member.guild.icon.url if member.guild.icon else None,
                )
                await traffic_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send traffic join log for {member} in guild {member.guild.id}: {e}")
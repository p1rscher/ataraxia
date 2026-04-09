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
        role_ids = settings['role_ids'] if settings['role_ids'] else []
        roles = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]
        
        if roles:
            try:
                await member.add_roles(*roles, reason="Autorole")
                role_names = [r.name for r in roles]
                logger.info(f"Assigned autoroles {role_names} to {member} in guild {member.guild.id}")
            except Exception as e:
                logger.error(f"Failed to assign autoroles to {member} in guild {member.guild.id}: {e}")

    # Send welcome message if configured
    welcome = await db.get_welcome_message(member.guild.id)
    if welcome:
        channel = member.guild.get_channel(welcome['channel_id'])
        if channel:
            try:
                text = welcome['message'].replace("{user}", member.mention).replace("{server}", member.guild.name)
                embed = discord.Embed(description=text, color=await get_guild_color(member.guild.id, 'color_welcome'))
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"{member.guild.name} • {member.guild.member_count} members")
                await channel.send(embed=embed)
                logger.info(f"Sent welcome message for {member} in guild {member.guild.id}")
            except Exception as e:
                logger.error(f"Failed to send welcome message for {member} in guild {member.guild.id}: {e}")

    
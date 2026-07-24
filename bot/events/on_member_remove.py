import discord
import logging
from typing import Optional
from core import database_pg as db
from utils.embeds import send_member_traffic_embed

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_member_remove(member: discord.Member):
    """Handle member leaving - send user traffic log"""

    try:
        await send_member_traffic_embed(member, 'leave')
    except Exception as e:
        logger.error(f"Failed to send traffic leave log for {member} in guild {member.guild.id}: {e}")

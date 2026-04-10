import discord
import logging
from typing import Optional
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None

async def on_member_remove(member: discord.Member):
    """Handle member leaving - send user traffic log"""

    # Send user traffic log if configured
    traffic_channel_id = await db.get_traffic_log_channel_id(member.guild.id)
    if traffic_channel_id:
        traffic_channel = member.guild.get_channel(traffic_channel_id)
        if traffic_channel and isinstance(traffic_channel, discord.TextChannel):
            try:
                joined_ts = int(member.joined_at.timestamp()) if member.joined_at else None
                color = await get_guild_color(member.guild.id)

                embed = discord.Embed(
                    title=f"{member.display_name} left the server",
                    color=color,
                )
                embed.add_field(
                    name="User",
                    value=member.mention,
                    inline=True,
                )
                if joined_ts:
                    embed.add_field(
                        name="Joined date",
                        value=f"<t:{joined_ts}:f> (<t:{joined_ts}:R>)",
                        inline=True,
                    )
                else:
                    embed.add_field(
                        name="Joined date",
                        value="Unknown",
                        inline=True,
                    )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(
                    text=f"{member.guild.name} • {member.guild.member_count} members",
                    icon_url=member.guild.icon.url if member.guild.icon else None,
                )
                await traffic_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send traffic leave log for {member} in guild {member.guild.id}: {e}")

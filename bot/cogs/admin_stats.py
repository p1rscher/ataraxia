import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)
db = None  # Database reference to be set from main.py

class AdminStatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="admin_stats")
    async def admin_stats(self, ctx: commands.Context):
        """Show bot statistics (owner only)"""
        if not await self.bot.is_owner(ctx.author):
            return
        
        try:
            # Get stats from database
            total_commands = await db.get_total_commands()
            daily_active_users = await db.get_daily_active_users()
            command_stats_7d = await db.get_command_stats(7)
            command_stats_1d = await db.get_command_stats(1)
            
            # Calculate bot stats
            total_servers = len(self.bot.guilds)
            total_users = sum(g.member_count for g in self.bot.guilds)
            
            # Create embed
            embed = discord.Embed(
                title="📊 Bot Statistics",
                color=await get_guild_color(ctx.guild.id if ctx.guild else None)
            )
            
            # General stats
            embed.add_field(name="🌐 Total Servers", value=f"{total_servers:,}", inline=True)
            embed.add_field(name="👥 Total Users", value=f"{total_users:,}", inline=True)
            embed.add_field(name="✨ Active Users (24h)", value=f"{daily_active_users:,}", inline=True)
            
            # Command stats
            embed.add_field(name="⚡ Total Commands", value=f"{total_commands:,}", inline=True)
            
            # Daily commands count
            daily_commands = sum(row['count'] for row in command_stats_1d)
            embed.add_field(name="📈 Commands (24h)", value=f"{daily_commands:,}", inline=True)
            
            # Weekly commands count
            weekly_commands = sum(row['count'] for row in command_stats_7d)
            embed.add_field(name="📊 Commands (7d)", value=f"{weekly_commands:,}", inline=True)
            
            # Top commands (last 7 days)
            if command_stats_7d:
                top_commands = "\n".join([
                    f"`{row['command_name']}`: {row['count']:,}x"
                    for row in command_stats_7d[:10]
                ])
                embed.add_field(
                    name="🏆 Top Commands (7 days)",
                    value=top_commands or "No data",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            logger.info(f"Admin stats viewed by {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error in admin_stats: {e}", exc_info=True)
            await ctx.send(f"❌ Error fetching stats: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminStatsCog(bot))
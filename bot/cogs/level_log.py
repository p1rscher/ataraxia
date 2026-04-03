# cogs/level_log.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class LevelLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    levellog_group = app_commands.Group(name="levellog", description="Manage level-up notification settings")
    
    @levellog_group.command(name="set", description="Set a channel for level-up notifications")
    @app_commands.describe(channel="The channel where level-up messages will be sent")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def levellog_set(self, ctx: discord.Interaction, channel: discord.TextChannel):
        """Set the level-up notification channel"""
        
        # Check if bot can send messages in that channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}!",
                ephemeral=True
            )
            return
        
        # Save to database
        await db.set_level_log_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="✅ Level Log Channel Set",
            description=f"Level-up notifications will now be sent to {channel.mention}",
            color=await get_guild_color(ctx.guild.id, 'color_level_up')
        )
        embed.set_footer(text="Use /levellog remove to disable this feature")
        
        await ctx.response.send_message(embed=embed)
        logger.info(f"Level log channel set to {channel.id} in guild {ctx.guild.id}")
    
    @levellog_group.command(name="remove", description="Remove the level-up notification channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def levellog_remove(self, ctx: discord.Interaction):
        """Remove the level-up notification channel"""
        
        # Check if configured
        current_channel_id = await db.get_level_log_channel_id(ctx.guild.id)
        if not current_channel_id:
            await ctx.response.send_message(
                "❌ No level log channel is currently configured!",
                ephemeral=True
            )
            return
        
        # Remove from database
        await db.remove_level_log_channel(ctx.guild.id)
        
        embed = discord.Embed(
            title="✅ Level Log Channel Removed",
            description="Level-up notifications will now be sent in the channel where XP was gained.",
            color=await get_guild_color(ctx.guild.id, 'color_level_up')
        )
        
        await ctx.response.send_message(embed=embed)
        logger.info(f"Level log channel removed in guild {ctx.guild.id}")
    
    @levellog_group.command(name="status", description="Check the current level-up notification settings")
    @app_commands.guild_only()
    async def levellog_status(self, ctx: discord.Interaction):
        """Show current level log configuration"""
        
        channel_id = await db.get_level_log_channel_id(ctx.guild.id)
        
        embed = discord.Embed(
            title="📊 Level Log Status",
            color=await get_guild_color(ctx.guild.id, 'color_level_up')
        )
        
        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                embed.description = f"✅ Level-up notifications are sent to {channel.mention}"
            else:
                embed.description = "⚠️ Configured channel no longer exists. Please set a new one."
        else:
            embed.description = "📝 No dedicated channel configured.\nLevel-ups are announced where XP is gained."
        
        embed.set_footer(text="Use /levellog set to configure a channel")
        
        await ctx.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LevelLogCog(bot))

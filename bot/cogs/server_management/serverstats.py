# cogs/serverstats.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import logging
from core import database_pg as db

from utils.font_converter import convert_font

logger = logging.getLogger(__name__)

class ServerStatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_updated = {}  # Dict to track last update times per channel
        logger.info("ServerStatsCog initialized - starting tasks")
        self.update_stats_fast.start()
        self.update_stats_slow.start()
        
    def cog_unload(self):
        logger.info("ServerStatsCog unloading - cancelling tasks")
        self.update_stats_fast.cancel()
        self.update_stats_slow.cancel()

    async def update_stat_channel(self, channel, stat_type, guild):
        """Update a single stat channel based on the stat_type"""
        try:
            # Check for rate limit (max. every 5 minutes)
            last_update = self.last_updated.get(channel.id)
            if last_update:
                now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                time_since_update = (now - last_update).total_seconds()
                if time_since_update < 300:  # at least 5 minutes between updates
                    logger.debug(f"Skipping update for {channel.id} (too soon, {time_since_update:.0f}s since last)")
                    return

            if stat_type == "members":
                # Total number of members
                count = guild.member_count
                new_name = f"👥 {await convert_font(f'Members: {count}', font='Math-Sans-Bold')}"
            elif stat_type == "users":
                # Only human members
                count = sum(1 for m in guild.members if not m.bot)
                new_name = f"👤 {await convert_font(f'Users: {count}', font='Math-Sans-Bold')}"
            elif stat_type == "bots":
                # Only bots
                count = sum(1 for m in guild.members if m.bot)
                new_name = f"🤖 {await convert_font(f'Bots: {count}', font='Math-Sans-Bold')}"
            elif stat_type == "online":
                # Only online members (requires Presence Intent)
                count = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
                new_name = f"🟢 {await convert_font(f'Online: {count}', font='Math-Sans-Bold')}"
            elif stat_type == "voice":
                # Members in voice channels
                count = sum(1 for m in guild.members if m.voice)
                count_str = str(count)
                new_name = f"🎤 {await convert_font(f'Voice: {count_str}', font='Math-Sans-Bold')}"
            else:
                logger.warning(f"Unknown stat_type: {stat_type}")
                return

            # Only update if the name has changed
            if channel.name != new_name:
                await channel.edit(name=new_name)
                self.last_updated[channel.id] = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                # logger.info(f"Updated {stat_type} channel {channel.id} in guild {guild.id}")
                
        except discord.Forbidden:
            logger.error(f"Keine Berechtigung, Kanal {channel.id} in Guild {guild.id} zu bearbeiten")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren von Statistik-Kanal {channel.id}: {e}", exc_info=True)

    @tasks.loop(minutes=10)
    async def update_stats_slow(self):
        """Updates stats that change less frequently (members, users, bots)"""
        # logger.info("update_stats_slow: Running iteration")
        try:
            for guild in self.bot.guilds:
                stat_channels = await db.get_stat_channels(guild.id)
                # logger.debug(f"update_stats_slow: Found {len(stat_channels)} stat channels in {guild.name}")
                for channel_id, stat_type in stat_channels:
                    if stat_type in ["members", "users", "bots"]:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            await self.update_stat_channel(channel, stat_type, guild)
                        else:
                            logger.warning(f"Channel {channel_id} not found in guild {guild.id}")
        except Exception as e:
            logger.error(f"Error in update_stats_slow: {e}", exc_info=True)

    @tasks.loop(minutes=5, seconds=5)
    async def update_stats_fast(self):
        """Updates stats that change frequently (online, voice)"""
        # logger.info("update_stats_fast: Running iteration")
        try:
            for guild in self.bot.guilds:
                stat_channels = await db.get_stat_channels(guild.id)
                # logger.debug(f"update_stats_fast: Found {len(stat_channels)} stat channels in {guild.name}")
                for channel_id, stat_type in stat_channels:
                    if stat_type in ["online", "voice"]:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            await self.update_stat_channel(channel, stat_type, guild)
                        else:
                            logger.warning(f"Channel {channel_id} not found in guild {guild.id}")
        except Exception as e:
            logger.error(f"Error in update_stats_fast: {e}", exc_info=True)

    @update_stats_slow.before_loop
    async def before_update_stats_slow(self):
        logger.info("update_stats_slow: Waiting for bot to be ready...")
        # Don't use wait_until_ready() - just check if bot is ready
        while not self.bot.is_ready():
            await asyncio.sleep(1)
        logger.info("update_stats_slow: Bot ready, sleeping 60 seconds before first run")
        await asyncio.sleep(60)
        logger.info("update_stats_slow: Starting first iteration")

    @update_stats_fast.before_loop
    async def before_update_stats_fast(self):
        logger.info("update_stats_fast: Waiting for bot to be ready...")
        # Don't use wait_until_ready() - just check if bot is ready
        while not self.bot.is_ready():
            await asyncio.sleep(1)
        logger.info("update_stats_fast: Bot ready, sleeping 30 seconds before first run")
        await asyncio.sleep(30)
        logger.info("update_stats_fast: Starting first iteration")
    
    @update_stats_slow.error
    async def update_stats_slow_error(self, error):
        logger.error(f"update_stats_slow task error: {error}", exc_info=True)
    
    @update_stats_fast.error
    async def update_stats_fast_error(self, error):
        logger.error(f"update_stats_fast task error: {error}", exc_info=True)

    async def handle_member_change(self, member):
        """Update stats on member changes"""
        stat_channels = await db.get_stat_channels(member.guild.id)
        for channel_id, stat_type in stat_channels:
            channel = member.guild.get_channel(channel_id)
            if not channel:
                continue
                
            # Check for rate limit (max. every 5 minutes for events)
            last_update = self.last_updated.get(channel_id)
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            if last_update and (now - last_update).total_seconds() < 300:
                continue
                
            await self.update_stat_channel(channel, stat_type, member.guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.handle_member_change(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.handle_member_change(member)

    @commands.hybrid_group(name="serverstats", description="Manage server statistics channels")
    async def serverstats_group(self, ctx: commands.Context):
        pass

    @serverstats_group.command(name="setup", description="Set up a channel for server statistics")
    @app_commands.describe(
        channel="The voice channel to display the statistics",
        stat_type="The type of statistic to display"
    )
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="Total Members", value="members"),
        app_commands.Choice(name="Users (no bots)", value="users"),
        app_commands.Choice(name="Bots", value="bots"),
        app_commands.Choice(name="Online Users", value="online"),
        app_commands.Choice(name="In Voice Channels", value="voice")
    ])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def serverstats_command(
        self, 
        ctx: commands.Context,
        channel: discord.VoiceChannel,
        stat_type: str
    ):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Only administrators can use this command.", ephemeral=True)
            return

        # Check bot permissions
        if not ctx.guild.me.guild_permissions.manage_channels:
            await ctx.send(
                "I need the 'Manage Channels' permission for this feature.",
                ephemeral=True
            )
            return

        # Save the configuration
        await db.set_stat_channel(ctx.guild.id, channel.id, stat_type)

        # Immediate update of the channel
        await self.update_stat_channel(channel, stat_type, ctx.guild)

        # Success message
        stats_map = {
            "members": "Total Members",
            "users": "Users (no bots)",
            "bots": "Bots",
            "online": "Online Users",
            "voice": "In Voice Channels"
        }
        
        await ctx.send(
            f"Channel {channel.mention} is now displaying the statistic **{stats_map.get(stat_type, stat_type)}**.\n"
            f"The statistic will be updated every 5 minutes.",
            ephemeral=True
        )

    @serverstats_group.command(name="reset", description="Remove a statistics channel")
    @app_commands.describe(channel="The channel to reset")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def resetstats_command(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel
    ):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Only administrators can use this command.", ephemeral=True)
            return
            
        await db.remove_stat_channel(channel.id)

        # Optional: Reset channel name
        try:
            await channel.edit(name="stats-reset")
            await ctx.send(
                f"Channel {channel.mention} has been reset.",
                ephemeral=True
            )
        except:
            await ctx.send(
                f"Channel has been removed from the database, but I couldn't change its name.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ServerStatsCog(bot))

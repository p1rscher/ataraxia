# cogs/bump_reminder.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import asyncio
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# Get database reference from main.py
db = None

class BumpReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("BumpReminder initialized - starting check_bump_reminders task")
        self.check_bump_reminders.start()
    
    def cog_unload(self):
        logger.info("BumpReminder unloading - cancelling task")
        self.check_bump_reminders.cancel()
    
    @commands.hybrid_group(name="bump", description="Manage bump reminder settings")
    async def bump_group(self, ctx: commands.Context):
        pass
    
    @bump_group.command(name="enable", description="Enable bump reminders for this server")
    @app_commands.describe(
        bump_role="The role to ping for bump reminders",
        reminder_channel="The channel where bump reminders will be sent"
    )
    @commands.guild_only()
    async def bump_enable(
        self, 
        ctx: commands.Context, 
        bump_role: discord.Role,
        reminder_channel: discord.TextChannel
    ):
        # Check admin permissions
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions for this command!", ephemeral=True)
            return
        
        await db.set_bump_settings(
            guild_id=ctx.guild.id,
            enabled=True,
            bump_role_id=bump_role.id,
            reminder_channel_id=reminder_channel.id
        )
        
        await ctx.send(
            f"✅ Bump reminder enabled!\n"
            f"📍 Role: {bump_role.mention}\n"
            f"📍 Channel: {reminder_channel.mention}\n\n"
            f"The bot will ping {bump_role.mention} 2 hours after the last `/bump` command.",
            ephemeral=True
        )

    @bump_group.command(name="disable", description="Disable bump reminders for this server")
    @commands.guild_only()
    async def bump_disable(self, ctx: commands.Context):
        # Check admin permissions
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions for this command!", ephemeral=True)
            return
        
        await db.set_bump_settings(
            guild_id=ctx.guild.id,
            enabled=False
        )
        
        await ctx.send("✅ Bump reminder disabled!", ephemeral=True)

    @bump_group.command(name="status", description="Show the status of the bump reminder system")
    @commands.guild_only()
    async def bump_status(self, ctx: commands.Context):
        settings = await db.get_bump_settings(ctx.guild.id)
        
        if not settings or not settings['enabled']:
            await ctx.send("❌ Bump reminder is not enabled!", ephemeral=True)
            return
        
        bump_role = ctx.guild.get_role(settings['bump_role_id'])
        reminder_channel = ctx.guild.get_channel(settings['reminder_channel_id'])
        
        embed = discord.Embed(title="📊 Bump Reminder Status", color=await get_guild_color(ctx.guild.id))
        embed.add_field(name="Status", value="✅ Enabled", inline=False)
        embed.add_field(name="Bump Role", value=bump_role.mention if bump_role else "❌ Not found", inline=True)
        embed.add_field(name="Reminder Channel", value=reminder_channel.mention if reminder_channel else "❌ Not found", inline=True)

        if settings['last_bump_time']:
            last_bump = settings['last_bump_time']
            # Naive datetime in UTC - add timezone info for display
            if last_bump.tzinfo is None:
                last_bump = last_bump.replace(tzinfo=timezone.utc)
            
            next_bump = last_bump + timedelta(hours=2)
            now = datetime.now(timezone.utc)
            
            time_left = next_bump - now

            embed.add_field(name="Last Bump", value=f"<t:{int(last_bump.timestamp())}:R>", inline=False)

            if time_left.total_seconds() > 0:
                minutes_left = int(time_left.total_seconds() / 60)
                embed.add_field(name="Next Reminder", value=f"In {minutes_left} minutes", inline=False)
            else:
                embed.add_field(name="Next Reminder", value="⏰ Due now!", inline=False)
        else:
            embed.add_field(name="Last Bump", value="No bumps detected yet", inline=False)
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @tasks.loop(minutes=1)
    async def check_bump_reminders(self):
        """Check every minute if a bump reminder is due"""
        logger.debug("check_bump_reminders: Running iteration")
        try:
            guilds = await db.get_all_bump_guilds()
            logger.debug(f"check_bump_reminders: Found {len(guilds)} guilds with bump enabled")
            
            for guild_settings in guilds:
                # Skip if no bump has occurred yet
                if not guild_settings['last_bump_time']:
                    continue
                
                last_bump = guild_settings['last_bump_time']
                # Naive datetime in UTC - add timezone info
                if last_bump.tzinfo is None:
                    last_bump = last_bump.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                time_since_bump = now - last_bump
                
                # Check if reminder was already sent (reminder_id is not None)
                is_reminded = guild_settings.get('reminder_id') is not None
                
                logger.debug(f"[Bump] Guild {guild_settings['guild_id']}: time_since_bump={time_since_bump}, is_reminded={is_reminded}")
                
                # Reset logic: If bump was recent (< 3 min) and reminder exists, it was already deleted by on_message
                # No need to do anything here, on_message handles deletion
                if time_since_bump < timedelta(minutes=3):
                    continue  # Don't send reminder for recent bumps
                
                # Reminder logic: If 2+ hours passed and NOT yet reminded, send reminder
                if time_since_bump >= timedelta(hours=2):
                    if not is_reminded:  # Only send if reminder_id is None (not yet reminded)
                        guild = self.bot.get_guild(guild_settings['guild_id'])
                        if not guild:
                            logger.warning(f"Guild {guild_settings['guild_id']} not found for bump reminder")
                            continue
                        
                        channel = guild.get_channel(guild_settings['reminder_channel_id'])
                        role = guild.get_role(guild_settings['bump_role_id'])
                        
                        if not channel:
                            logger.warning(f"Channel {guild_settings['reminder_channel_id']} not found in guild {guild.id}")
                            continue
                        
                        if not role:
                            logger.warning(f"Role {guild_settings['bump_role_id']} not found in guild {guild.id}")
                            continue
                        
                        if channel and role:
                            try:
                                msg = await channel.send(
                                    f"{role.mention} It's time for the next `/bump`! 🚀",
                                    allowed_mentions=discord.AllowedMentions(roles=True)
                                )
                                # Save reminder message ID
                                await db.update_reminded_id(guild.id, msg.id)
                                logger.info(f"Sent bump reminder for guild {guild.id} (msg_id: {msg.id})")
                            except Exception as e:
                                logger.error(f"Error sending bump reminder in guild {guild.id}: {e}")
                    else:
                        logger.debug(f"Skipping guild {guild_settings['guild_id']} - already reminded")
        
        except Exception as e:
            logger.error(f"Error in check_bump_reminders: {e}", exc_info=True)
    
    @check_bump_reminders.before_loop
    async def before_check_bump_reminders(self):
        logger.info("check_bump_reminders: Waiting for bot to be ready...")
        # Don't use wait_until_ready() - just check if bot is ready
        while not self.bot.is_ready():
            await asyncio.sleep(1)
        logger.info("check_bump_reminders: Bot ready, starting task")

async def setup(bot):
    await bot.add_cog(BumpReminder(bot))

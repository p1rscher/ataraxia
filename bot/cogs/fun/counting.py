# cogs/counting.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class CountingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="counting", description="Counting channel management")
    async def counting_group(self, ctx: commands.Context):
        pass

    @counting_group.command(name="setup")
    @app_commands.describe(channel="The channel to use as counting channel")
    @commands.has_permissions(administrator=True)
    async def counting_setup(self, interaction: commands.Context, channel: discord.TextChannel):
        """Setup a counting channel"""
        try:
            await self.bot.counting_cache.set_channel(interaction.guild.id, channel.id)
            
            embed = discord.Embed(
                title="✅ Counting Channel Setup",
                description=f"Counting channel has been set to {channel.mention}\n\nStart counting from **1**!",
                color=await get_guild_color(interaction.guild.id, 'color_counting')
            )
            await interaction.send(embed=embed)
            
            # Send initial message in counting channel
            await channel.send("🔢 **Start counting from 1!**")
            
        except Exception as e:
            logger.error(f"Error setting up counting channel: {e}")
            await interaction.send("❌ An error occurred while setting up the counting channel.", ephemeral=True)

    @counting_group.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def counting_remove(self, interaction: commands.Context):
        """Remove the counting channel setup"""
        try:
            await self.bot.counting_cache.remove_channel(interaction.guild.id)
            
            embed = discord.Embed(
                title="✅ Counting Channel Removed",
                description="The counting channel has been removed.",
                color=await get_guild_color(interaction.guild.id, 'color_counting')
            )
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing counting channel: {e}")
            await interaction.send("❌ An error occurred while removing the counting channel.", ephemeral=True)

    @counting_group.command(name="status")
    async def counting_status(self, interaction: commands.Context):
        """Check the current counting status"""
        try:
            settings = await self.bot.counting_cache.get_settings(interaction.guild.id)
            
            if not settings:
                await interaction.send("❌ No counting channel has been set up yet.", ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(settings['channel_id'])
            current_number = settings['current_number']
            high_score = settings['high_score']
            last_user_id = settings['last_user_id']
            
            embed = discord.Embed(
                title="🔢 Counting Status",
                color=await get_guild_color(interaction.guild.id, 'color_counting')
            )
            
            if channel:
                embed.add_field(name="Channel", value=channel.mention, inline=False)
            else:
                embed.add_field(name="Channel", value="Channel not found", inline=False)
            
            embed.add_field(name="Current Number", value=str(current_number), inline=True)
            embed.add_field(name="High Score", value=str(high_score), inline=True)
            
            if last_user_id:
                last_user = interaction.guild.get_member(last_user_id)
                if last_user:
                    embed.add_field(name="Last Counter", value=last_user.mention, inline=False)
            
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking counting status: {e}")
            await interaction.send("❌ An error occurred while checking the counting status.", ephemeral=True)

    @counting_group.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def counting_reset(self, interaction: commands.Context):
        """Reset the counting channel to 0"""
        try:
            await self.bot.counting_cache.reset(interaction.guild.id)
            
            embed = discord.Embed(
                title="✅ Counting Reset",
                description="The counting has been reset to 0. Start counting from **1** again!",
                color=await get_guild_color(interaction.guild.id, 'color_counting')
            )
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error resetting counting: {e}")
            await interaction.send("❌ An error occurred while resetting the counting.", ephemeral=True)

    @counting_group.command(name="leaderboard")
    async def counting_leaderboard(self, interaction: commands.Context):
        """Show the counting leaderboard"""
        try:
            await self.bot.counting_cache.flush_pending(guild_id=interaction.guild.id)
            leaderboard = await self.bot.db.get_counting_leaderboard(interaction.guild.id, limit=10)
            
            if not leaderboard:
                await interaction.send("❌ No counting data available yet.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🏆 Counting Leaderboard",
                description="Top 10 counters in this server",
                color=await get_guild_color(interaction.guild.id, 'color_counting')
            )
            
            for idx, (user_id, count) in enumerate(leaderboard, start=1):
                user = interaction.guild.get_member(user_id)
                if user:
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                    embed.add_field(
                        name=f"{medal} {user.display_name}",
                        value=f"{count} correct counts",
                        inline=False
                    )
            
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing counting leaderboard: {e}")
            await interaction.send("❌ An error occurred while showing the leaderboard.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages in counting channels"""
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        try:
            result = await self.bot.counting_cache.process_message(
                message.guild.id,
                message.channel.id,
                message.author.id,
                message.content,
            )

            if result.status == "ignore":
                return

            if result.status == "invalid":
                await message.delete()
                return

            if result.status == "same_user":
                await message.delete()
                return

            if result.status == "correct":
                await message.add_reaction("✅")
                if result.milestone_reached:
                    embed = discord.Embed(
                        title="🎉 New Milestone!",
                        description=f"**{result.current_number}** - Well done!",
                        color=await get_guild_color(message.guild.id, 'color_counting')
                    )
                    await message.channel.send(embed=embed)
                return

            if result.status == "wrong":
                embed = discord.Embed(
                    title="❌ Wrong Number!",
                    description=(
                        f"{message.author.mention} ruined it at **{result.current_number}**!\n\n"
                        f"The next number was **{result.expected_number}**, not **{result.attempted_number}**.\n"
                        f"High Score: **{result.high_score}**\n\n"
                        f"Start over from **1**!"
                    ),
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in counting on_message: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CountingCog(bot))

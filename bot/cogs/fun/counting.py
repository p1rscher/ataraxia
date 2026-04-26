# cogs/counting.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# Database reference (set in main.py)
db = None

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
            await db.set_counting_channel(interaction.guild.id, channel.id)
            
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
            await db.remove_counting_channel(interaction.guild.id)
            
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
            settings = await db.get_counting_settings(interaction.guild.id)
            
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
            await db.reset_counting(interaction.guild.id)
            
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
            leaderboard = await db.get_counting_leaderboard(interaction.guild.id, limit=10)
            
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
            settings = await db.get_counting_settings(message.guild.id)
            
            if not settings or settings['channel_id'] != message.channel.id:
                return
            
            current_number = settings['current_number']
            last_user_id = settings['last_user_id']
            high_score = settings['high_score']

            # Try to parse the number
            try:
                number = int(message.content.strip())
            except ValueError:
                await message.delete()
                try:
                    await message.author.send(
                        f"❌ Only numbers are allowed in the counting channel of {message.guild.name}!\n"
                        f"Current number: **{current_number}**"
                    )
                except:
                    pass
                return
            
            # Check if the same user counted twice in a row
            if last_user_id == message.author.id:
                await message.delete()
                try:
                    await message.author.send(
                        f"❌ You cannot count twice in a row in {message.guild.name}!\n"
                        f"Current number: **{current_number}**"
                    )
                except:
                    pass
                return
            
            # Check if it's the correct number
            expected_number = current_number + 1
            
            if number == expected_number:
                # Correct number!
                await message.add_reaction("✅")
                
                # Update database
                await db.update_counting(
                    message.guild.id,
                    new_number=expected_number,
                    last_user_id=message.author.id
                )
                
                # Update user stats
                await db.increment_user_counting(message.guild.id, message.author.id)
                
                # Check for new high score
                if expected_number > high_score:
                    await db.update_counting_highscore(message.guild.id, expected_number)
                    
                    if expected_number % 100 == 0:  # Celebrate every 100
                        embed = discord.Embed(
                            title="🎉 New High Score!",
                            description=f"**{expected_number}** - Well done!",
                            color=await get_guild_color(message.guild.id, 'color_counting')
                        )
                        await message.channel.send(embed=embed)
                
            else:
                # Wrong number!
                await message.delete()
                
                embed = discord.Embed(
                    title="❌ Wrong Number!",
                    description=(
                        f"{message.author.mention} ruined it at **{current_number}**!\n\n"
                        f"The next number was **{expected_number}**, not **{number}**.\n"
                        f"High Score: **{high_score}**\n\n"
                        f"Start over from **1**!"
                    ),
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                
                # Reset counting
                await db.reset_counting(message.guild.id)
                
        except Exception as e:
            logger.error(f"Error in counting on_message: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CountingCog(bot))

# cogs/level_roles.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# Database reference (set in main.py)
db = None

class LevelRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="levelrole", description="Level role management")
    async def levelrole_group(self, ctx: commands.Context):
        pass

    @levelrole_group.command(name="add")
    @app_commands.describe(
        level="The level to assign the role at",
        role="The role to give at this level"
    )
    @commands.has_permissions(administrator=True)
    async def levelrole_add(self, interaction: commands.Context, level: int, role: discord.Role):
        """Add a role reward for reaching a specific level"""
        if level < 1:
            await interaction.send("❌ Level must be at least 1.", ephemeral=True)
            return
        
        # Check if bot can manage this role
        if role >= interaction.guild.me.top_role:
            await interaction.send(
                f"❌ I cannot manage {role.mention} because it's higher than or equal to my highest role.",
                ephemeral=True
            )
            return
        
        if role.managed:
            await interaction.send(
                f"❌ {role.mention} is a managed role (bot/integration role) and cannot be assigned.",
                ephemeral=True
            )
            return
        
        try:
            await db.add_level_role(interaction.guild.id, level, role.id)
            
            embed = discord.Embed(
                title="✅ Level Role Added",
                description=f"Users will now receive {role.mention} when reaching **Level {level}**",
                color=await get_guild_color(interaction.guild.id)
            )
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error adding level role: {e}")
            await interaction.send("❌ An error occurred while adding the level role.", ephemeral=True)

    @levelrole_group.command(name="remove")
    @app_commands.describe(level="The level to remove the role reward from")
    @commands.has_permissions(administrator=True)
    async def levelrole_remove(self, interaction: commands.Context, level: int):
        """Remove a level role reward"""
        try:
            role_id = await db.get_level_role(interaction.guild.id, level)
            
            if not role_id:
                await interaction.send(f"❌ No role is configured for Level {level}.", ephemeral=True)
                return
            
            await db.remove_level_role(interaction.guild.id, level)
            
            role = interaction.guild.get_role(role_id)
            role_mention = role.mention if role else f"Role ID: {role_id}"
            
            embed = discord.Embed(
                title="✅ Level Role Removed",
                description=f"Removed {role_mention} from **Level {level}**",
                color=await get_guild_color(interaction.guild.id)
            )
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing level role: {e}")
            await interaction.send("❌ An error occurred while removing the level role.", ephemeral=True)

    @levelrole_group.command(name="list")
    async def levelrole_list(self, interaction: commands.Context):
        """List all level role rewards"""
        try:
            level_roles = await db.get_all_level_roles(interaction.guild.id)
            
            if not level_roles:
                await interaction.send("❌ No level roles have been configured yet.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎯 Level Role Rewards",
                description="Roles that are automatically given when reaching specific levels",
                color=await get_guild_color(interaction.guild.id)
            )
            
            # Sort by level
            level_roles.sort(key=lambda x: x[0])
            
            for level, role_id in level_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    embed.add_field(
                        name=f"Level {level}",
                        value=f"{role.mention}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"Level {level}",
                        value=f"⚠️ Role not found (ID: {role_id})",
                        inline=True
                    )
            
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing level roles: {e}")
            await interaction.send("❌ An error occurred while listing level roles.", ephemeral=True)

    @levelrole_group.command(name="sync")
    @app_commands.describe(
        user="The user to sync level roles for (leave empty to sync all users)"
    )
    @commands.has_permissions(administrator=True)
    async def levelrole_sync(self, interaction: commands.Context, user: discord.Member = None):
        """Sync level roles for a user or all users"""
        await interaction.defer(ephemeral=True)
        
        try:
            level_roles = await db.get_all_level_roles(interaction.guild.id)
            
            if not level_roles:
                await interaction.send("❌ No level roles have been configured yet.", ephemeral=True)
                return
            
            # Get all configured level role IDs for removal
            level_role_ids = [role_id for _, role_id in level_roles]
            
            if user:
                # Sync single user
                await self._sync_user_roles(interaction.guild, user, level_roles, level_role_ids)
                await interaction.send(f"✅ Synced level roles for {user.mention}", ephemeral=True)
            else:
                # Sync all users
                synced = 0
                for member in interaction.guild.members:
                    if not member.bot:
                        await self._sync_user_roles(interaction.guild, member, level_roles, level_role_ids)
                        synced += 1
                
                await interaction.send(f"✅ Synced level roles for {synced} users", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error syncing level roles: {e}")
            await interaction.send("❌ An error occurred while syncing level roles.", ephemeral=True)

    @commands.hybrid_command(name="leaderboard")
    @app_commands.describe(limit="Number of users to show (default: 10)")
    async def leaderboard(self, interaction: commands.Context, limit: int = 10):
        """Show the server XP leaderboard"""
        if limit < 1 or limit > 25:
            await interaction.send("❌ Limit must be between 1 and 25.", ephemeral=True)
            return
        
        try:
            leaderboard_data = await db.get_leaderboard(interaction.guild.id, limit)
            
            if not leaderboard_data:
                await interaction.send("❌ No level data available yet.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🏆 XP Leaderboard",
                description=f"Top {len(leaderboard_data)} members by XP",
                color=await get_guild_color(interaction.guild.id)
            )
            
            leaderboard_text = ""
            for idx, (user_id, xp, level) in enumerate(leaderboard_data, start=1):
                member = interaction.guild.get_member(user_id)
                if member:
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
                    leaderboard_text += f"{medal} **{member.display_name}** - Level {level} ({xp:,} XP)\n"
            
            embed.description = leaderboard_text if leaderboard_text else "No data available"
            embed.set_footer(text=f"Requested by {interaction.author.display_name}", icon_url=interaction.author.display_avatar.url)
            
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")
            await interaction.send("❌ An error occurred while showing the leaderboard.", ephemeral=True)

    @commands.hybrid_command(name="rank")
    @app_commands.describe(user="The user to check rank for (leave empty for yourself)")
    async def rank(self, interaction: commands.Context, user: discord.Member = None):
        """Check your rank and XP progress"""
        target = user or interaction.author
        
        try:
            level_data = await db.get_level(target.id, interaction.guild.id)
            
            if not level_data:
                await interaction.send(
                    f"❌ {target.mention} has no XP data yet.",
                    ephemeral=True
                )
                return
            
            current_level = level_data['level']
            current_xp = level_data['xp']
            multiplier = level_data['multiplier']
            
            # Calculate XP for current and next level
            from utils.xp_calculator import calculate_xp_needed
            current_level_xp = await calculate_xp_needed(current_level) if current_level > 0 else 0
            next_level_xp = await calculate_xp_needed(current_level + 1)
            
            # XP progress in current level
            xp_in_level = current_xp - current_level_xp
            xp_needed_in_level = next_level_xp - current_level_xp
            progress_percentage = (xp_in_level / xp_needed_in_level) * 100 if xp_needed_in_level > 0 else 0
            
            # Get rank
            leaderboard = await db.get_leaderboard(interaction.guild.id, 1000)
            rank = None
            for idx, (uid, _, _) in enumerate(leaderboard, start=1):
                if uid == target.id:
                    rank = idx
                    break
            
            embed = discord.Embed(
                title=f"📊 Rank - {target.display_name}",
                color=await get_guild_color(interaction.guild.id)
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            
            if rank:
                embed.add_field(name="🏆 Rank", value=f"#{rank}", inline=True)
            
            embed.add_field(name="⭐ Level", value=str(current_level), inline=True)
            embed.add_field(name="💎 Total XP", value=f"{current_xp:,}", inline=True)
            
            # Progress bar
            bar_length = 10
            filled = int((progress_percentage / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            embed.add_field(
                name="📈 Progress to Next Level",
                value=f"{bar} {progress_percentage:.1f}%\n{xp_in_level:,} / {xp_needed_in_level:,} XP",
                inline=False
            )
            
            if multiplier != 1.0:
                embed.add_field(name="✨ XP Multiplier", value=f"{multiplier}x", inline=True)
            
            await interaction.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing rank: {e}", exc_info=True)
            await interaction.send("❌ An error occurred while showing the rank.", ephemeral=True)

    async def _sync_user_roles(self, guild: discord.Guild, member: discord.Member, level_roles: list, level_role_ids: list):
        """Internal method to sync roles for a single user"""
        try:
            # Get user's current level
            level_data = await db.get_level(member.id, guild.id)
            if not level_data:
                return
            
            user_level = level_data['level']
            
            # Find which role they should have (highest level they've reached)
            role_to_add = None
            highest_reached_level = 0
            
            for level, role_id in level_roles:
                if level <= user_level and level > highest_reached_level:
                    highest_reached_level = level
                    role_to_add = guild.get_role(role_id)
            
            # Remove all other level roles
            roles_to_remove = []
            for role_id in level_role_ids:
                role = guild.get_role(role_id)
                if role and role in member.roles:
                    if role != role_to_add:
                        roles_to_remove.append(role)
            
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Level role sync")
            
            # Add the correct role if they don't have it
            if role_to_add and role_to_add not in member.roles:
                await member.add_roles(role_to_add, reason=f"Reached Level {highest_reached_level}")
                
        except Exception as e:
            logger.error(f"Error syncing roles for {member}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelRolesCog(bot))

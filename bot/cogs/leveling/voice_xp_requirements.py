# cogs/voice_xp_requirements.py

"""
Ataraxia Discord Bot
Copyright (c) 2025 p1rscher
Licensed under the AGPLv3 License - see LICENSE file for details.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands
from core import database_pg as db
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class VoiceXPRequirements(commands.Cog):
    """Configure Voice XP requirements for your server"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Group for voice XP requirement commands
    @commands.hybrid_group(
        name="voicexp-requirements",
        description="Configure Voice XP requirements"
    )
    async def requirements_group(self, ctx: commands.Context):
        pass
    
    @requirements_group.command(name="view", description="View current Voice XP requirements")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_requirements(self, interaction: commands.Context):
        """View current Voice XP requirements for the server"""
        
        requirements = await db.get_voice_xp_requirements(interaction.guild.id)
        
        embed = discord.Embed(
            title="🎤 Voice XP Requirements",
            description="Current requirements for earning Voice XP",
            color=await get_guild_color(interaction.guild.id)
        )
        
        embed.add_field(
            name="AFK Status",
            value="✅ Must NOT be AFK" if requirements['require_non_afk'] else "❌ Can be AFK",
            inline=True
        )
        
        embed.add_field(
            name="Deafened Status",
            value="✅ Must NOT be deafened" if requirements['require_non_deaf'] else "❌ Can be deafened",
            inline=True
        )
        
        embed.add_field(
            name="Muted Status",
            value="✅ Must NOT be muted" if requirements['require_non_muted'] else "❌ Can be muted",
            inline=True
        )
        
        embed.add_field(
            name="Others in Channel",
            value="✅ Must have others in channel" if requirements['require_others_in_channel'] else "❌ Can be alone",
            inline=True
        )
        
        embed.set_footer(text=f"Server: {interaction.guild.name}")
        
        await interaction.send(embed=embed)
    
    @requirements_group.command(name="set-afk", description="Set whether AFK users can earn Voice XP")
    @app_commands.describe(
        allow="Should AFK users earn Voice XP? (False = AFK users don't get XP)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_afk_requirement(self, interaction: commands.Context, allow: bool):
        """Set AFK requirement for Voice XP"""
        
        # Note: allow=True means they CAN be AFK, so require_non_afk=False
        require_non_afk = not allow
        
        await db.set_voice_xp_requirement(interaction.guild.id, 'require_non_afk', require_non_afk)
        
        status = "❌ will NOT earn" if require_non_afk else "✅ will earn"
        
        embed = discord.Embed(
            title="✅ AFK Requirement Updated",
            description=f"AFK users {status} Voice XP",
            color=await get_guild_color(interaction.guild.id)
        )
        
        await interaction.send(embed=embed)
    
    @requirements_group.command(name="set-deaf", description="Set whether deafened users can earn Voice XP")
    @app_commands.describe(
        allow="Should deafened users earn Voice XP? (False = deafened users don't get XP)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_deaf_requirement(self, interaction: commands.Context, allow: bool):
        """Set deafened requirement for Voice XP"""
        
        # Note: allow=True means they CAN be deaf, so require_non_deaf=False
        require_non_deaf = not allow
        
        await db.set_voice_xp_requirement(interaction.guild.id, 'require_non_deaf', require_non_deaf)
        
        status = "❌ will NOT earn" if require_non_deaf else "✅ will earn"
        
        embed = discord.Embed(
            title="✅ Deaf Requirement Updated",
            description=f"Deafened users {status} Voice XP",
            color=await get_guild_color(interaction.guild.id)
        )
        
        await interaction.send(embed=embed)
    
    @requirements_group.command(name="set-muted", description="Set whether muted users can earn Voice XP")
    @app_commands.describe(
        allow="Should muted users earn Voice XP? (False = muted users don't get XP)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_muted_requirement(self, interaction: commands.Context, allow: bool):
        """Set muted requirement for Voice XP"""
        
        # Note: allow=True means they CAN be muted, so require_non_muted=False
        require_non_muted = not allow
        
        await db.set_voice_xp_requirement(interaction.guild.id, 'require_non_muted', require_non_muted)
        
        status = "❌ will NOT earn" if require_non_muted else "✅ will earn"
        
        embed = discord.Embed(
            title="✅ Muted Requirement Updated",
            description=f"Muted users {status} Voice XP",
            color=await get_guild_color(interaction.guild.id)
        )
        
        await interaction.send(embed=embed)
    
    @requirements_group.command(name="set-alone", description="Set whether users alone in a channel can earn Voice XP")
    @app_commands.describe(
        allow="Should users alone in a channel earn Voice XP? (False = must have others)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_alone_requirement(self, interaction: commands.Context, allow: bool):
        """Set alone-in-channel requirement for Voice XP"""
        
        # Note: allow=True means they CAN be alone, so require_others_in_channel=False
        require_others_in_channel = not allow
        
        await db.set_voice_xp_requirement(interaction.guild.id, 'require_others_in_channel', require_others_in_channel)
        
        status = "✅ will earn" if not require_others_in_channel else "❌ will NOT earn"
        
        embed = discord.Embed(
            title="✅ Alone-in-Channel Requirement Updated",
            description=f"Users alone in a voice channel {status} Voice XP",
            color=await get_guild_color(interaction.guild.id)
        )
        
        await interaction.send(embed=embed)
    
    @requirements_group.command(name="reset", description="Reset all Voice XP requirements to defaults")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_requirements(self, interaction: commands.Context):
        """Reset all Voice XP requirements to defaults"""
        
        # Defaults: require_non_afk=True, require_non_deaf=True, require_non_muted=False, require_others_in_channel=True
        await db.set_all_voice_xp_requirements(
            interaction.guild.id,
            require_non_afk=True,
            require_non_deaf=True,
            require_non_muted=False,
            require_others_in_channel=True
        )
        
        embed = discord.Embed(
            title="✅ Voice XP Requirements Reset",
            description="All Voice XP requirements have been reset to defaults",
            color=await get_guild_color(interaction.guild.id)
        )
        
        embed.add_field(name="AFK Users", value="❌ Will NOT earn XP", inline=True)
        embed.add_field(name="Deafened Users", value="❌ Will NOT earn XP", inline=True)
        embed.add_field(name="Muted Users", value="✅ Will earn XP", inline=True)
        embed.add_field(name="Alone in Channel", value="❌ Will NOT earn XP", inline=True)
        
        await interaction.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VoiceXPRequirements(bot))

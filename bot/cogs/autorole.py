# cogs/autorole.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class AutoroleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    autorole_group = app_commands.Group(name="autorole", description="Automatic role assignment for new members")

    @autorole_group.command(name="enable", description="Enable autorole system for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_enable(self, ctx: discord.Interaction):
        """Enable autorole system"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.set_autorole_enabled(ctx.guild_id, True)
        await ctx.response.send_message("✅ Autorole system enabled!", ephemeral=True)
        logger.info(f"Autorole enabled in guild {ctx.guild_id}")

    @autorole_group.command(name="disable", description="Disable autorole system for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_disable(self, ctx: discord.Interaction):
        """Disable autorole system"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.set_autorole_enabled(ctx.guild_id, False)
        await ctx.response.send_message("✅ Autorole system disabled!", ephemeral=True)
        logger.info(f"Autorole disabled in guild {ctx.guild_id}")

    @autorole_group.command(name="add", description="Add a role to autorole list")
    @app_commands.describe(role="The role to automatically assign to new members")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_add(self, ctx: discord.Interaction, role: discord.Role):
        """Add role to autorole"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        
        # Check if bot can assign the role
        if role.position >= ctx.guild.me.top_role.position:
            await ctx.response.send_message(
                f"❌ The role {role.mention} is higher than my highest role. I cannot assign this role.",
                ephemeral=True
            )
            return
        
        await db.add_autorole(ctx.guild_id, role.id)
        await ctx.response.send_message(
            f"✅ Added {role.mention} to autorole list!",
            ephemeral=True
        )
        logger.info(f"Added autorole {role.name} (ID: {role.id}) in guild {ctx.guild_id}")

    @autorole_group.command(name="remove", description="Remove a role from autorole list")
    @app_commands.describe(role="The role to remove from autorole")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_remove(self, ctx: discord.Interaction, role: discord.Role):
        """Remove role from autorole"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.remove_autorole(ctx.guild_id, role.id)
        await ctx.response.send_message(
            f"✅ Removed {role.mention} from autorole list!",
            ephemeral=True
        )
        logger.info(f"Removed autorole {role.name} (ID: {role.id}) from guild {ctx.guild_id}")

    @autorole_group.command(name="list", description="List all autoroles configured for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_list(self, ctx: discord.Interaction):
        """List all autoroles"""
        settings = await db.get_autorole_settings(ctx.guild_id)
        
        if not settings:
            await ctx.response.send_message(
                "❌ Autorole system is not configured for this server.",
                ephemeral=True
            )
            return
        
        enabled_status = "✅ Enabled" if settings['enabled'] else "❌ Disabled"
        role_ids = settings['role_ids'] if settings['role_ids'] else []
        
        if not role_ids:
            role_list = "No roles configured"
        else:
            roles = [ctx.guild.get_role(rid) for rid in role_ids]
            role_list = "\n".join([f"• {role.mention}" for role in roles if role])
        
        embed = discord.Embed(
            title="🎭 Autorole Configuration",
            description=f"**Status:** {enabled_status}\n\n**Roles:**\n{role_list}",
            color=await get_guild_color(ctx.guild_id)
        )
        
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @autorole_group.command(name="clear", description="Clear all autoroles for this server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def autorole_clear(self, ctx: discord.Interaction):
        """Clear all autoroles"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.clear_autoroles(ctx.guild_id)
        await ctx.response.send_message("✅ Cleared all autoroles!", ephemeral=True)
        logger.info(f"Cleared all autoroles in guild {ctx.guild_id}")


async def setup(bot):
    await bot.add_cog(AutoroleCog(bot))

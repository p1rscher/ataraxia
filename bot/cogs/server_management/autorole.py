# cogs/autorole.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from typing import Literal
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class AutoroleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="autorole", description="Automatic role assignment for new members")
    async def autorole_group(self, ctx: commands.Context):
        pass

    @autorole_group.command(name="enable", description="Enable autorole system for this server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_enable(self, ctx: commands.Context):
        """Enable autorole system"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.set_autorole_enabled(ctx.guild.id, True)
        await ctx.send("✅ Autorole system enabled!", ephemeral=True)
        logger.info(f"Autorole enabled in guild {ctx.guild.id}")

    @autorole_group.command(name="disable", description="Disable autorole system for this server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_disable(self, ctx: commands.Context):
        """Disable autorole system"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.set_autorole_enabled(ctx.guild.id, False)
        await ctx.send("✅ Autorole system disabled!", ephemeral=True)
        logger.info(f"Autorole disabled in guild {ctx.guild.id}")

    @autorole_group.command(name="add", description="Add a role to autorole list")
    @app_commands.describe(
        role="The role to automatically assign to new members",
        target="Who should get this role (user, bot, or both)"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_add(self, ctx: commands.Context, role: discord.Role, target: Literal["user", "bot", "both"] = "user"):
        """Add role to autorole"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        # Check if bot can assign the role
        if role.position >= ctx.guild.me.top_role.position:
            await ctx.send(
                f"❌ The role {role.mention} is higher than my highest role. I cannot assign this role.",
                ephemeral=True
            )
            return
        
        await db.add_autorole(ctx.guild.id, role.id, target)
        await ctx.send(
            f"✅ Added {role.mention} to autorole list for **{target}**!",
            ephemeral=True
        )
        logger.info(f"Added autorole {role.name} (ID: {role.id}) for {target} in guild {ctx.guild.id}")

    @autorole_group.command(name="remove", description="Remove a role from autorole list")
    @app_commands.describe(
        role="The role to remove from autorole",
        target="Which list to remove from (user, bot, or both)"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_remove(self, ctx: commands.Context, role: discord.Role, target: Literal["user", "bot", "both"] = "user"):
        """Remove role from autorole"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.remove_autorole(ctx.guild.id, role.id, target)
        await ctx.send(
            f"✅ Removed {role.mention} from autorole list for **{target}**!",
            ephemeral=True
        )
        logger.info(f"Removed autorole {role.name} (ID: {role.id}) for {target} in guild {ctx.guild.id}")

    @autorole_group.command(name="list", description="List all autoroles configured for this server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_list(self, ctx: commands.Context):
        """List all autoroles"""
        settings = await db.get_autorole_settings(ctx.guild.id)
        
        if not settings:
            await ctx.send(
                "❌ Autorole system is not configured for this server.",
                ephemeral=True
            )
            return
        
        enabled_status = "✅ Enabled" if settings['enabled'] else "❌ Disabled"
        
        user_role_ids = settings['user_role_ids'] if settings.get('user_role_ids') else []
        bot_role_ids = settings['bot_role_ids'] if settings.get('bot_role_ids') else []
        
        def format_roles(role_ids):
            if not role_ids:
                return "No roles configured"
            roles = [ctx.guild.get_role(rid) for rid in role_ids]
            return "\n".join([f"• {role.mention}" for role in roles if role]) or "No roles configured"

        embed = discord.Embed(
            title="🎭 Autorole Configuration",
            description=f"**Status:** {enabled_status}",
            color=await get_guild_color(ctx.guild.id)
        )
        
        embed.add_field(name="👤 User Roles", value=format_roles(user_role_ids), inline=False)
        embed.add_field(name="🤖 Bot Roles", value=format_roles(bot_role_ids), inline=False)
        
        await ctx.send(embed=embed, ephemeral=True)

    @autorole_group.command(name="clear", description="Clear autoroles for this server")
    @app_commands.describe(target="Which list to clear (user, bot, or all)")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole_clear(self, ctx: commands.Context, target: Literal["user", "bot", "all"] = "all"):
        """Clear autoroles"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.clear_autoroles(ctx.guild.id, target)
        await ctx.send(f"✅ Cleared autorole list for **{target}**!", ephemeral=True)
        logger.info(f"Cleared autoroles for {target} in guild {ctx.guild.id}")


async def setup(bot):
    await bot.add_cog(AutoroleCog(bot))

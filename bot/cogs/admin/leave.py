# cogs/admin/leave.py
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class LeaveCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="leave", hidden=True)
    async def leave(self, ctx: commands.Context, guild_id: int = None):
        """Leave a server (Prefix command, owner only)"""
        
        # Check if user is bot owner
        if not await self.bot.is_owner(ctx.author):
            return
        
        target_guild = None
        if guild_id:
            target_guild = self.bot.get_guild(guild_id)
            if not target_guild:
                await ctx.send(f"❌ Could not find a server with ID `{guild_id}`.")
                return
        else:
            target_guild = ctx.guild
            if not target_guild:
                await ctx.send("❌ Please provide a server ID or use this command in a server.")
                return

        try:
            # Prepare confirmation message
            confirm_msg = f"👋 Leaving server: **{target_guild.name}** (`{target_guild.id}`)."
            if target_guild == ctx.guild:
                confirm_msg += " Goodbye!"
            
            # Send the message before leaving the guild
            await ctx.send(confirm_msg)
            
            logger.info(f"Leave command invoked by {ctx.author} for guild {target_guild.name} ({target_guild.id})")
            
            # Leave the guild
            await target_guild.leave()
            
        except discord.Forbidden:
            # This is technically possible if the guild is not accessible, though bots can usually leave
            await ctx.send(f"❌ I don't have permission to leave **{target_guild.name}**.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logger.error(f"Error leaving guild {target_guild.id}: {e}")


async def setup(bot):
    await bot.add_cog(LeaveCog(bot))

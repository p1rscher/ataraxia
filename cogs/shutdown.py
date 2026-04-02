# cogs/shutdown.py
import discord
from discord.ext import commands
import logging
import asyncio
from utils.close import graceful_shutdown

logger = logging.getLogger(__name__)


class ShutdownCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="shutdown", hidden=True)
    async def shutdown(self, ctx: commands.Context):
        """Shutdown the bot (prefix command, hidden from help)"""
        
        # Check if user is bot owner
        if not await self.bot.is_owner(ctx.author):
            return
        
        await ctx.send("Shutting down...")
        logger.info(f"Shutdown command invoked by {ctx.author}")
        
        # Delay to ensure the message is sent before shutdown
        await asyncio.sleep(0.5)
        await graceful_shutdown(self.bot)


async def setup(bot):
    await bot.add_cog(ShutdownCog(bot))

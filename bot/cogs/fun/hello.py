# cogs/hello.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands

class HelloCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="hello", description="Responds with Hello!")
    async def hello(self, ctx: commands.Context):
        await ctx.send("Hello!")

async def setup(bot):
    await bot.add_cog(HelloCog(bot))

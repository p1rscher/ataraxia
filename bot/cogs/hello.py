# cogs/hello.py
import discord
from discord.ext import commands
from discord import app_commands

class HelloCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Responds with Hello!")
    async def hello(self, ctx: discord.Interaction):
        await ctx.response.send_message("Hello!")

async def setup(bot):
    await bot.add_cog(HelloCog(bot))

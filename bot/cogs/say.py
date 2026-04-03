# cogs/say.py
import discord
from discord.ext import commands
from discord import app_commands

class SayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="say", description="Responds with a message")
    async def say(self, ctx: discord.Interaction, message: str):
        
        # Check admin permissions
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions for this command!", ephemeral=True)
            return
        
        channel = ctx.channel
        await channel.send(message)
        await ctx.response.send_message("Message sent!", ephemeral=True)



async def setup(bot):
    await bot.add_cog(SayCog(bot))

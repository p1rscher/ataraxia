# cogs/about.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands


class AboutCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.hybrid_command(name="about", description="About Ataraxia Bot")
    async def about(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🤖 Ataraxia Bot",
            description="Advanced community management bot",
            color=discord.Color(5793266)
        )
        
        embed.add_field(
            name="Developer",
            value="pirscher (Git: p1rscher) & ur.fav.kuma (Git: zKxma)",
            inline=False
        )
        
        embed.add_field(
            name="Website",
            value="[ataraxia-bot.com](https://ataraxia-bot.com)",
            inline=False
        )
        
        embed.add_field(
            name="Open Source Libraries",
            value=(
                "• [discord.py](https://github.com/Rapptz/discord.py) (MIT)\n"
                "• [asyncpg](https://github.com/MagicStack/asyncpg) (Apache 2.0)\n"
                "• [python-dotenv](https://github.com/theskumar/python-dotenv) (BSD-3)\n"
                "• [groq](https://github.com/groq/groq-python) (Apache 2.0)\n"
                "• [Python](https://www.python.org/) 3.11+ (PSF License)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="License",
            value="MIT License © 2025-2026 pirscher (Git: p1rscher)\nSee [full licenses](https://ataraxia-bot.com/licenses)",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AboutCog(bot))

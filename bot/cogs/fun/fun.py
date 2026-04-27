# cogs/fun.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
import aiohttp

logger = logging.getLogger(__name__)

class FunCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="8ball")
    async def eightball(self, ctx: commands.Context, question: str):
        responses = ["Yes!", "No!", "Maybe...", "Ask again later"]
        await ctx.send(f"🎱 {random.choice(responses)}")

    @commands.hybrid_command(name="flipcoin")
    async def coinflip(self, ctx: commands.Context):
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f"🪙 {result}!")

    @commands.hybrid_command(name="poll")
    async def poll(self, ctx: commands.Context, question: str, options: str):
        # Creates poll with reactions
        # /poll "Best color?" "Red, Blue, Green"
        option_list = [opt.strip() for opt in options.split(",")]
        if len(option_list) < 2 or len(option_list) > 10:
            await ctx.send("❌ You must provide between 2 and 10 options.", ephemeral=True)
            return

        await ctx.send(f"📊 Poll: {question}\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(option_list)]))
        poll_message = await ctx.original_response()
        for i in range(len(option_list)):
            await poll_message.add_reaction(discord.PartialEmoji.from_str(f"{i+1}️⃣"))

    @commands.hybrid_command(name="joke", description="Tells a fresh joke directly from the internet")
    async def joke(self, ctx: commands.Context):
        # We enforce safe/clean jokes by default through query parameters
        url = "https://v2.jokeapi.dev/joke/Any?safe-mode"
        
        await getattr(ctx, "interaction", ctx).response.defer() if hasattr(ctx, "interaction") and ctx.interaction else None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    data = await response.json()
                    
                    if data.get("error"):
                        await ctx.send("The API threw a fit and refused to tell a joke. Try again later!", ephemeral=True)
                        return
                    
                    embed = discord.Embed(title="🎭 Here's a Joke", color=discord.Color.gold())
                    
                    if data["type"] == "twopart":
                        embed.description = f"**{data['setup']}**\n\n||{data['delivery']}||"
                    else:
                        embed.description = f"**{data['joke']}**"
                    
                    embed.set_footer(text=f"Category: {data['category']}")
                    
                    if hasattr(ctx, "interaction") and ctx.interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                        
        except Exception as e:
            logger.error(f"Error fetching joke: {e}")
            msg = "Failed to reach the joke repository. The comedian is out sick today."
            if hasattr(ctx, "interaction") and ctx.interaction:
                await ctx.interaction.followup.send(msg)
            else:
                await ctx.send(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(FunCog(bot))
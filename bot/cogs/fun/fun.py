# cogs/fun.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import random
import logging

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

async def setup(bot: commands.Bot):
    await bot.add_cog(FunCog(bot))
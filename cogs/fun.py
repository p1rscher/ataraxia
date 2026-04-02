# cogs/fun.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging

logger = logging.getLogger(__name__)

class FunCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball")
    async def eightball(self, ctx: discord.Interaction, question: str):
        responses = ["Yes!", "No!", "Maybe...", "Ask again later"]
        await ctx.response.send_message(f"🎱 {random.choice(responses)}")

    @app_commands.command(name="coinflip")
    async def coinflip(self, ctx: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await ctx.response.send_message(f"🪙 {result}!")

    @app_commands.command(name="poll")
    async def poll(self, ctx: discord.Interaction, question: str, options: str):
        # Erstellt Poll mit Reactions
        # /poll "Best color?" "Red, Blue, Green"
        option_list = [opt.strip() for opt in options.split(",")]
        if len(option_list) < 2 or len(option_list) > 10:
            await ctx.response.send_message("❌ You must provide between 2 and 10 options.", ephemeral=True)
            return

        poll_message = await ctx.response.send_message(f"📊 Poll: {question}\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(option_list)]))
        for i in range(len(option_list)):
            await poll_message.add_reaction(discord.PartialEmoji.from_str(f"{i+1}️⃣"))

        await ctx.response.send_message("✅ Poll created!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(FunCog(bot))
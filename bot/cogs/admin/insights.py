# cogs/insights.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class InsightsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="info", description="Get information about server and members")
    async def info_group(self, ctx: commands.Context):
        pass
    
    @info_group.command(name="server", description="Show server information")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context):
        embed = discord.Embed(title=f"📊 {ctx.guild.name}", color=await get_guild_color(ctx.guild.id))
        embed.add_field(name="Members", value=ctx.guild.member_count)
        embed.add_field(name="Created", value=ctx.guild.created_at.strftime("%Y-%m-%d"))
        embed.add_field(name="Boost Level", value=ctx.guild.premium_tier)
        # + Charts, Graphs, Activity stats
        await ctx.send(embed=embed)

    @info_group.command(name="member", description="Show member information")
    @app_commands.describe(member="The member to get information about")
    @commands.guild_only()
    async def memberinfo(self, ctx: commands.Context, member: discord.Member):
        # Account age, join date, roles, activity
        embed = discord.Embed(title=f"👤 {member.display_name}", color=await get_guild_color(ctx.guild.id))
        embed.add_field(name="Account Age", value=f"{(discord.utils.utcnow() - member.created_at).days} days")
        embed.add_field(name="Join Date", value=member.joined_at.strftime("%Y-%m-%d"))
        embed.add_field(name="Roles", value=", ".join([role.name for role in member.roles if role.name != "@everyone"]), inline=False)
        embed.add_field(name="Activity", value=str(member.activity) if member.activity else "None")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(InsightsCog(bot))

# cogs/insights.py
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class InsightsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    info_group = app_commands.Group(name="info", description="Get information about server and members")
    
    @info_group.command(name="server", description="Show server information")
    @app_commands.guild_only()
    async def serverinfo(self, ctx: discord.Interaction):
        embed = discord.Embed(title=f"📊 {ctx.guild.name}")
        embed.add_field(name="Members", value=ctx.guild.member_count)
        embed.add_field(name="Created", value=ctx.guild.created_at.strftime("%Y-%m-%d"))
        embed.add_field(name="Boost Level", value=ctx.guild.premium_tier)
        # + Charts, Graphs, Activity stats
        await ctx.response.send_message(embed=embed)

    @info_group.command(name="member", description="Show member information")
    @app_commands.describe(member="The member to get information about")
    @app_commands.guild_only()
    async def memberinfo(self, ctx: discord.Interaction, member: discord.Member):
        # Account age, join date, roles, activity
        embed = discord.Embed(title=f"👤 {member.display_name}")
        embed.add_field(name="Account Age", value=f"{(discord.utils.utcnow() - member.created_at).days} days")
        embed.add_field(name="Join Date", value=member.joined_at.strftime("%Y-%m-%d"))
        embed.add_field(name="Roles", value=", ".join([role.name for role in member.roles if role.name != "@everyone"]), inline=False)
        embed.add_field(name="Activity", value=str(member.activity) if member.activity else "None")
        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(InsightsCog(bot))

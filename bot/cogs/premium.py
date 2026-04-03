# cogs/premium.py
import discord
from discord import app_commands
from discord.ext import commands
from core import database_pg as db
import logging

logger = logging.getLogger(__name__)


class PremiumCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    premium_group = app_commands.Group(name="premium", description="Manage premium features and subscriptions")
    
    @premium_group.command(name="info", description="View premium tiers and benefits")
    async def premium_info(self, ctx: discord.Interaction):
        embed = discord.Embed(
            title="💎 Ataraxia Premium",
            description="Unlock faster AI, more features, and support development!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🆓 Free Tier",
            value=(
                "• 90s AI cooldown\n"
                "• 500 token responses\n"
                "• All basic features"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💎 Premium - $5/month",
            value=(
                "• **30s AI cooldown** (3x faster!)\n"
                "• 1000 token responses\n"
                "• Priority support\n"
                "• Premium badge"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👑 Premium+ - $7/month",
            value=(
                "• **10s AI cooldown** (9x faster!)\n"
                "• 2000 token responses\n"
                "• GPT-4 access (coming soon)\n"
                "• Custom AI personality\n"
                "• Early access to new features"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎁 How to Purchase",
            value=(
                "Contact: p1rscher@ataraxia-bot.com\n"
                "Or visit: https://ataraxia-bot.com/premium\n"
                "Payment via PayPal/Stripe"
            ),
            inline=False
        )
        
        embed.set_footer(text="All revenue supports hosting costs & development ❤️")
        
        await ctx.response.send_message(embed=embed)
    
    @premium_group.command(name="redeem", description="Redeem a premium code")
    @app_commands.describe(code="Your premium code")
    async def redeem(self, ctx: discord.Interaction, code: str):
        # TODO: Implement code verification
        # For now, placeholder:
        await ctx.response.send_message(
            "❌ Invalid code. Purchase premium at https://ataraxia-bot.com/premium",
            ephemeral=True
        )
    
    @premium_group.command(name="grant", description="[ADMIN] Grant premium to a user")
    @app_commands.describe(
        user="User to grant premium",
        tier="Premium tier",
        days="Duration in days"
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="Premium", value="premium"),
        app_commands.Choice(name="Premium+", value="premium_plus"),
    ])
    async def grant_premium(
        self, 
        ctx: discord.Interaction, 
        user: discord.User,
        tier: str,
        days: int = 30
    ):
        # Check if user is bot owner
        if not self.bot.is_owner(ctx.user):
            await ctx.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        await db.set_user_premium(user.id, tier, days)
        
        await ctx.response.send_message(
            f"✅ Granted **{tier}** to {user.mention} for {days} days!",
            ephemeral=True
        )
        
        # DM the user
        try:
            dm_embed = discord.Embed(
                title="🎉 Premium Activated!",
                description=f"You've been granted **{tier.replace('_', ' ').title()}** for {days} days!",
                color=discord.Color.gold()
            )
            dm_embed.add_field(
                name="Benefits",
                value=f"Check `/ai status` to see your new perks!",
                inline=False
            )
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled


async def setup(bot):
    await bot.add_cog(PremiumCog(bot))
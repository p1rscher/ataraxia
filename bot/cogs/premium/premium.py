# cogs/premium.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands
from core import database_pg as db
import logging
import base64
import mimetypes
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class PremiumCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _to_data_uri(filename: str, content_type: str | None, raw_bytes: bytes) -> str:
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        encoded = base64.b64encode(raw_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    async def _patch_current_member(self, guild_id: int, payload: dict, reason: str | None = None):
        route = discord.http.Route("PATCH", "/guilds/{guild_id}/members/@me", guild_id=guild_id)
        return await self.bot.http.request(route, json=payload, reason=reason)

    @staticmethod
    def _can_manage_server_profile(interaction: commands.Context) -> bool:
        perms = interaction.author.guild_permissions
        return bool(perms and (perms.manage_guild or perms.administrator))

    async def _has_premium_access(self, user: discord.abc.User) -> bool:
        if await self.bot.is_owner(user):
            return True
        tier = await db.get_user_premium_tier(user.id)
        return tier in ("premium", "premium_plus")

    async def _get_current_member(self, guild_id: int, user_id: int):
        route = discord.http.Route(
            "GET",
            "/guilds/{guild_id}/members/{user_id}",
            guild_id=guild_id,
            user_id=user_id,
        )
        return await self.bot.http.request(route)
    
    @commands.hybrid_group(name="premium", description="Manage premium features and subscriptions")
    async def premium_group(self, ctx: commands.Context):
        pass
    
    @premium_group.command(name="info", description="View premium tiers and benefits")
    async def premium_info(self, ctx: commands.Context):
        embed = discord.Embed(
            title="💎 Ataraxia Premium",
            description="Unlock faster AI, more features, and support development!",
            color=await get_guild_color(ctx.guild.id if ctx.guild.id else None)
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
        
        await ctx.send(embed=embed)
    
    @premium_group.command(name="redeem", description="Redeem a premium code")
    @app_commands.describe(code="Your premium code")
    async def redeem(self, ctx: commands.Context, code: str):
        # TODO: Implement code verification
        # For now, placeholder:
        await ctx.send(
            "❌ Invalid code. ",#Purchase premium at https://ataraxia-bot.com/premium",
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
        ctx: commands.Context, 
        user: discord.User,
        tier: str,
        days: int = 30
    ):
        # Check if user is bot owner
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("❌ Admin only!", ephemeral=True)
            return
        
        await db.set_user_premium(user.id, tier, days)
        
        await ctx.send(
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

    @premium_group.command(name="set_server_profile", description="Set this bot's guild-specific profile")
    @commands.has_permissions(manage_guild=True, administrator=True)
    @app_commands.describe(
        nickname="Guild-only nickname for the bot",
        bio="Guild-only bio for the bot",
        avatar="Guild-only avatar image (PNG/JPG/GIF, max 8MB)",
        banner="Guild-only banner image (PNG/JPG/GIF, max 8MB)"
    )
    async def set_server_profile(
        self,
        ctx: commands.Context,
        nickname: str | None = None,
        bio: str | None = None,
        avatar: discord.Attachment | None = None,
        banner: discord.Attachment | None = None
    ):
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not (nickname or bio or avatar or banner):
            await ctx.send("❌ Provide at least one field to update.", ephemeral=True)
            return

        if not self._can_manage_server_profile(ctx):
            await ctx.send("❌ You need **Manage Server** to use this.", ephemeral=True)
            return

        if not await self._has_premium_access(ctx.author):
            await ctx.send(
                "❌ This feature requires **Premium**. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=True, thinking=True)

        payload = {}

        if nickname is not None:
            payload["nick"] = nickname[:32] if nickname else None
        if bio is not None:
            payload["bio"] = bio[:190] if bio else None

        for field_name, attachment in (("avatar", avatar), ("banner", banner)):
            if not attachment:
                continue

            if attachment.size > 8 * 1024 * 1024:
                await ctx.send(
                    f"❌ `{field_name}` exceeds 8MB. Please upload a smaller image.",
                    ephemeral=True
                )
                return

            content_type = (attachment.content_type or "").lower()
            allowed = ("image/png", "image/jpeg", "image/jpg", "image/gif")
            if content_type and content_type not in allowed:
                await ctx.send(
                    f"❌ `{field_name}` must be PNG, JPG, or GIF.",
                    ephemeral=True
                )
                return

            raw = await attachment.read()
            payload[field_name] = self._to_data_uri(attachment.filename, attachment.content_type, raw)

        reason = f"Requested by {ctx.author} ({ctx.author.id})"

        try:
            await self._patch_current_member(ctx.guild.id, payload, reason=reason)
        except discord.HTTPException as e:
            logger.exception("Failed to update guild profile for guild_id=%s", ctx.guild.id)
            await ctx.send(
                f"❌ Discord API rejected the update: `{e.status}` - {e.text}",
                ephemeral=True
            )
            return

        await ctx.send("✅ Updated guild-specific bot profile.", ephemeral=True)

    @premium_group.command(name="reset_server_profile", description="Reset this bot's guild-specific profile fields")
    @commands.has_permissions(manage_guild=True, administrator=True)
    @app_commands.describe(
        avatar="Reset guild-specific avatar",
        banner="Reset guild-specific banner",
        bio="Reset guild-specific bio",
        nickname="Reset guild-specific nickname"
    )
    async def reset_server_profile(
        self,
        ctx: commands.Context,
        avatar: bool = False,
        banner: bool = False,
        bio: bool = False,
        nickname: bool = False
    ):
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not self._can_manage_server_profile(ctx):
            await ctx.send("❌ You need **Manage Server** to use this.", ephemeral=True)
            return

        if not await self._has_premium_access(ctx.author):
            await ctx.send(
                "❌ This feature requires **Premium**. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        payload = {}
        if avatar:
            payload["avatar"] = None
        if banner:
            payload["banner"] = None
        if bio:
            payload["bio"] = None
        if nickname:
            payload["nick"] = None

        if not payload:
            await ctx.send("❌ Select at least one field to reset.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True, thinking=True)

        reason = f"Requested by {ctx.author} ({ctx.author.id})"

        try:
            await self._patch_current_member(ctx.guild.id, payload, reason=reason)
        except discord.HTTPException as e:
            logger.exception("Failed to reset guild profile for guild_id=%s", ctx.guild.id)
            await ctx.send(
                f"❌ Discord API rejected the reset: `{e.status}` - {e.text}",
                ephemeral=True
            )
            return

        await ctx.send("✅ Reset selected guild-specific bot profile fields.", ephemeral=True)

    @premium_group.command(name="view_server_profile", description="View this bot's guild-specific profile")
    @commands.has_permissions(manage_guild=True, administrator=True)
    async def view_server_profile(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not self._can_manage_server_profile(ctx):
            await ctx.send("❌ You need **Manage Server** to use this.", ephemeral=True)
            return

        if not await self._has_premium_access(ctx.author):
            await ctx.send(
                "❌ This feature requires **Premium**. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=True, thinking=True)

        try:
            if not self.bot.user:
                await ctx.send("❌ Bot user is not ready yet.", ephemeral=True)
                return
            member = await self._get_current_member(ctx.guild.id, self.bot.user.id)
        except discord.HTTPException as e:
            await ctx.send(
                f"❌ Failed to read server profile: `{e.status}` - {e.text}",
                ephemeral=True
            )
            return

        bot_user_id = self.bot.user.id if self.bot.user else None
        avatar_hash = member.get("avatar")
        banner_hash = member.get("banner")
        nick = member.get("nick")
        bio = member.get("bio")

        avatar_url = None
        banner_url = None

        if bot_user_id and avatar_hash:
            avatar_ext = "gif" if str(avatar_hash).startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/guilds/{ctx.guild.id}/users/{bot_user_id}/avatars/{avatar_hash}.{avatar_ext}?size=1024"

        if bot_user_id and banner_hash:
            banner_ext = "gif" if str(banner_hash).startswith("a_") else "png"
            banner_url = f"https://cdn.discordapp.com/guilds/{ctx.guild.id}/users/{bot_user_id}/banners/{banner_hash}.{banner_ext}?size=1024"

        embed = discord.Embed(
            title="Server Profile (Bot)",
            color=await get_guild_color(ctx.guild.id)
        )
        embed.add_field(name="Nickname", value=nick or "Not set", inline=False)
        embed.add_field(name="Bio", value=bio or "Not set", inline=False)
        embed.add_field(name="Guild Avatar", value=avatar_url or "Not set", inline=False)
        embed.add_field(name="Guild Banner", value=banner_url or "Not set", inline=False)

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        if banner_url:
            embed.set_image(url=banner_url)

        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PremiumCog(bot))
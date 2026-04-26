import discord
from discord.ext import commands
from discord import app_commands
import logging
import re
from datetime import timedelta
from typing import Optional
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

def parse_duration(duration_str: str) -> timedelta | None:
    """Parses a duration string like '1d', '2h', '30m' into a timedelta.
    Returns None if the format is invalid."""
    pattern = re.fullmatch(r'(\d+)(d|h|m)', duration_str.strip().lower())
    if not pattern:
        return None
    value, unit = int(pattern.group(1)), pattern.group(2)
    if unit == 'd':
        return timedelta(days=value)
    if unit == 'h':
        return timedelta(hours=value)
    if unit == 'm':
        return timedelta(minutes=value)

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_mod_log(self, guild: discord.Guild, embed: discord.Embed):
        """Send an embed to the guild's configured moderation log channel, if set."""
        channel_id = await db.get_mod_log_channel_id(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Missing permissions to send mod log in channel {channel_id} (guild {guild.id})")

    async def _try_delete_command(self, ctx: commands.Context):
        """Try to delete the invoking prefix command message for a cleaner look."""
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ──────────────────────────────────────────────────────
    # /warn  &  Atx.warn
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(user="The member to warn", reason="Reason for the warning")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, user: discord.Member, *, reason: str):
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot warn a member with an equal or higher role.", ephemeral=True)
            return

        warning_id = await db.add_warning(ctx.guild.id, user.id, ctx.author.id, reason)
        warnings = await db.get_warnings(ctx.guild.id, user.id)

        color = await get_guild_color(ctx.guild.id)

        # Ephemeral confirmation to the moderator
        confirm_embed = discord.Embed(title="⚠️ Member Warned", color=color)
        confirm_embed.add_field(name="Member", value=user.mention, inline=True)
        confirm_embed.add_field(name="Reason", value=reason, inline=False)
        confirm_embed.set_footer(text=f"Warning #{warning_id} • {len(warnings)} total warning(s)")
        await ctx.send(embed=confirm_embed, ephemeral=True)

        # Mod log channel embed
        log_embed = discord.Embed(title="⚠️ Member Warned", color=color)
        log_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_footer(text=f"Warning #{warning_id} • {len(warnings)} total warning(s)")
        log_embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_mod_log(ctx.guild, log_embed)

        try:
            dm_embed = discord.Embed(
                title=f"⚠️ You were warned in {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=color
            )
            dm_embed.set_footer(text=f"Warning #{warning_id} • {len(warnings)} total warning(s)")
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        logger.info(f"Warned {user} (#{warning_id}) in guild {ctx.guild.id} by {ctx.author}")

    # ──────────────────────────────────────────────────────
    # /warnings  &  Atx.warnings
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="warnings", description="View warnings for a member")
    @app_commands.describe(user="The member to check")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, user: discord.Member):
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return

        rows = await db.get_warnings(ctx.guild.id, user.id)
        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(title=f"⚠️ Warnings for {user.display_name}", color=color)
        embed.set_thumbnail(url=user.display_avatar.url)

        if not rows:
            embed.description = "No warnings on record."
        else:
            for row in rows:
                mod = ctx.guild.get_member(row['moderator_id'])
                mod_str = mod.mention if mod else f"<@{row['moderator_id']}>"
                ts = int(row['created_at'].timestamp())
                embed.add_field(
                    name=f"Warning #{row['id']} — <t:{ts}:R>",
                    value=f"**Reason:** {row['reason']}\n**Moderator:** {mod_str}",
                    inline=False
                )
        embed.set_footer(text=f"{len(rows)} total warning(s)")
        await ctx.send(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────────────
    # /delwarn  &  Atx.delwarn
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="delwarn", description="Delete a warning by ID")
    @app_commands.describe(warning_id="The warning ID to delete")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def delwarn(self, ctx: commands.Context, warning_id: int):
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return

        deleted = await db.delete_warning(ctx.guild.id, warning_id)
        if deleted:
            await ctx.send(f"✅ Warning `#{warning_id}` deleted.", ephemeral=True)
        else:
            await ctx.send(f"❌ Warning `#{warning_id}` not found.", ephemeral=True)

    # ──────────────────────────────────────────────────────
    # /kick  &  Atx.kick
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @app_commands.describe(user="The member to kick", reason="Reason for the kick")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, user: discord.Member, *, reason: str):
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("❌ You need the **Kick Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot kick a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.kick_members:
            await ctx.send("❌ I don't have permission to kick members.", ephemeral=True)
            return

        try:
            dm_embed = discord.Embed(
                title=f"👢 You were kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.orange()
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await user.kick(reason=f"{ctx.author}: {reason}")

        color = await get_guild_color(ctx.guild.id)

        # Ephemeral confirmation to the moderator
        confirm_embed = discord.Embed(title="👢 Member Kicked", color=color)
        confirm_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        confirm_embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=confirm_embed, ephemeral=True)

        # Mod log channel embed
        log_embed = discord.Embed(title="👢 Member Kicked", color=color)
        log_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_mod_log(ctx.guild, log_embed)

        logger.info(f"Kicked {user} from guild {ctx.guild.id} by {ctx.author}")

    # ──────────────────────────────────────────────────────
    # /ban  &  Atx.ban
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        user="The member to ban",
        reason="Reason for the ban",
        duration="Duration of the ban (e.g. 7d, 24h, 30m). Leave empty for permanent."
    )
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, user: discord.Member, duration: Optional[str] = None, *, reason: Optional[str] = None):
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("❌ You need the **Ban Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot ban a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send("❌ I don't have permission to ban members.", ephemeral=True)
            return

        # Smart Detection: If duration is NOT a valid time format, treat it as the start of the reason
        if duration and parse_duration(duration) is None:
            reason = f"{duration} {reason or ''}".strip()
            duration = None
        
        reason = reason or "No reason provided"
        delta = None
        if duration:
            delta = parse_duration(duration)
            if delta is None:
                await ctx.send("❌ Invalid duration format. Use `1d`, `12h` or `30m`.", ephemeral=True)
                return

        try:
            dm_embed = discord.Embed(
                title=f"🔨 You were banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Duration:** {duration or 'Permanent'}",
                color=discord.Color.red()
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await user.ban(reason=f"{ctx.author}: {reason}", delete_message_days=0)

        color = await get_guild_color(ctx.guild.id)

        # Ephemeral confirmation to the moderator
        confirm_embed = discord.Embed(title="🔨 Member Banned", color=color)
        confirm_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        confirm_embed.add_field(name="Duration", value=duration or "Permanent", inline=True)
        confirm_embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=confirm_embed, ephemeral=True)

        # Mod log channel embed
        log_embed = discord.Embed(title="🔨 Member Banned", color=color)
        log_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Duration", value=duration or "Permanent", inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_mod_log(ctx.guild, log_embed)

        logger.info(f"Banned {user} ({duration or 'permanent'}) from guild {ctx.guild.id} by {ctx.author}")

        if delta:
            import asyncio
            await asyncio.sleep(delta.total_seconds())
            try:
                await ctx.guild.unban(user, reason="Temporary ban expired")
                logger.info(f"Unbanned {user} after {duration} in guild {ctx.guild.id}")
            except discord.NotFound:
                pass

    # ──────────────────────────────────────────────────────
    # /timeout  &  Atx.timeout
    # ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="timeout", description="Timeout a member (max 28 days)")
    @app_commands.describe(
        user="The member to timeout",
        reason="Reason for the timeout",
        duration="Duration (e.g. 1d, 2h, 30m) — max 28d"
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: Optional[str] = None):
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot timeout a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.moderate_members:
            await ctx.send("❌ I don't have permission to timeout members.", ephemeral=True)
            return

        # Smart Detection: For timeout, a duration is REQUIRED. 
        # If it's invalid, the user likely typed `Atx.timeout @user reason` without a duration.
        if parse_duration(duration) is None:
            await ctx.send(f"❌ **Invalid or missing duration.**\nUsage: `{ctx.prefix}timeout @user <duration> [reason]` (e.g. `10m`, `1d`)", ephemeral=True)
            return

        delta = parse_duration(duration)
        if delta > timedelta(days=28):
            await ctx.send("❌ Discord limits timeouts to a maximum of **28 days**.", ephemeral=True)
            return

        reason = reason or "No reason provided"
        await user.timeout(delta, reason=f"{ctx.author}: {reason}")

        color = await get_guild_color(ctx.guild.id)

        # Ephemeral confirmation to the moderator
        confirm_embed = discord.Embed(title="🔇 Member Timed Out", color=color)
        confirm_embed.add_field(name="Member", value=user.mention, inline=True)
        confirm_embed.add_field(name="Duration", value=duration, inline=True)
        confirm_embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=confirm_embed, ephemeral=True)

        # Mod log channel embed
        log_embed = discord.Embed(title="🔇 Member Timed Out", color=color)
        log_embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Duration", value=duration, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_mod_log(ctx.guild, log_embed)

        try:
            dm_embed = discord.Embed(
                title=f"🔇 You were timed out in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Duration:** {duration}",
                color=discord.Color.orange()
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        logger.info(f"Timed out {user} for {duration} in guild {ctx.guild.id} by {ctx.author}")

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))

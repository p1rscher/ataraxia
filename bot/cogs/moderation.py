import discord
from discord.ext import commands
from discord import app_commands
import logging
import re
from datetime import timedelta
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

    # ──────────────────────────────────────────────────────
    # /warn
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(user="The member to warn", reason="Reason for the warning")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def warn(self, ctx: discord.Interaction, user: discord.Member, reason: str):
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.response.send_message("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.user.top_role and ctx.user.id != ctx.guild.owner_id:
            await ctx.response.send_message("❌ You cannot warn a member with an equal or higher role.", ephemeral=True)
            return

        warning_id = await db.add_warning(ctx.guild_id, user.id, ctx.user.id, reason)
        warnings = await db.get_warnings(ctx.guild_id, user.id)

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(title="⚠️ Member Warned", color=color)
        embed.add_field(name="Member", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Warning #{warning_id} • {len(warnings)} total warning(s)")
        embed.set_thumbnail(url=user.display_avatar.url)

        await ctx.response.send_message(embed=embed)

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

        logger.info(f"Warned {user} (#{warning_id}) in guild {ctx.guild_id} by {ctx.user}")

    # ──────────────────────────────────────────────────────
    # /warnings
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(user="The member to check")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def warnings(self, ctx: discord.Interaction, user: discord.Member):
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.response.send_message("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return

        rows = await db.get_warnings(ctx.guild_id, user.id)
        color = await get_guild_color(ctx.guild_id)
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
        await ctx.response.send_message(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────────────
    # /delwarn
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="delwarn", description="Delete a warning by ID")
    @app_commands.describe(warning_id="The warning ID to delete")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def delwarn(self, ctx: discord.Interaction, warning_id: int):
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.response.send_message("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return

        deleted = await db.delete_warning(ctx.guild_id, warning_id)
        if deleted:
            await ctx.response.send_message(f"✅ Warning `#{warning_id}` deleted.", ephemeral=True)
        else:
            await ctx.response.send_message(f"❌ Warning `#{warning_id}` not found.", ephemeral=True)

    # ──────────────────────────────────────────────────────
    # /kick
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(user="The member to kick", reason="Reason for the kick")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(self, ctx: discord.Interaction, user: discord.Member, reason: str):
        if not ctx.user.guild_permissions.kick_members:
            await ctx.response.send_message("❌ You need the **Kick Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.user.top_role and ctx.user.id != ctx.guild.owner_id:
            await ctx.response.send_message("❌ You cannot kick a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.kick_members:
            await ctx.response.send_message("❌ I don't have permission to kick members.", ephemeral=True)
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

        await user.kick(reason=f"{ctx.user}: {reason}")

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(title="👢 Member Kicked", color=color)
        embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        embed.add_field(name="Moderator", value=ctx.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.response.send_message(embed=embed)
        logger.info(f"Kicked {user} from guild {ctx.guild_id} by {ctx.user}")

    # ──────────────────────────────────────────────────────
    # /ban
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        user="The member to ban",
        reason="Reason for the ban",
        duration="Duration of the ban (e.g. 7d, 24h, 30m). Leave empty for permanent."
    )
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, ctx: discord.Interaction, user: discord.Member, reason: str, duration: str = None):
        if not ctx.user.guild_permissions.ban_members:
            await ctx.response.send_message("❌ You need the **Ban Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.user.top_role and ctx.user.id != ctx.guild.owner_id:
            await ctx.response.send_message("❌ You cannot ban a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
            return

        delta = None
        if duration:
            delta = parse_duration(duration)
            if delta is None:
                await ctx.response.send_message("❌ Invalid duration format. Use `1d`, `12h` or `30m`.", ephemeral=True)
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

        await user.ban(reason=f"{ctx.user}: {reason}", delete_message_days=0)

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(title="🔨 Member Banned", color=color)
        embed.add_field(name="Member", value=f"{user} ({user.id})", inline=True)
        embed.add_field(name="Moderator", value=ctx.user.mention, inline=True)
        embed.add_field(name="Duration", value=duration or "Permanent", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.response.send_message(embed=embed)
        logger.info(f"Banned {user} ({duration or 'permanent'}) from guild {ctx.guild_id} by {ctx.user}")

        if delta:
            import asyncio
            await asyncio.sleep(delta.total_seconds())
            try:
                await ctx.guild.unban(user, reason="Temporary ban expired")
                logger.info(f"Unbanned {user} after {duration} in guild {ctx.guild_id}")
            except discord.NotFound:
                pass

    # ──────────────────────────────────────────────────────
    # /timeout
    # ──────────────────────────────────────────────────────

    @app_commands.command(name="timeout", description="Timeout a member (max 28 days)")
    @app_commands.describe(
        user="The member to timeout",
        reason="Reason for the timeout",
        duration="Duration (e.g. 1d, 2h, 30m) — max 28d"
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def timeout(self, ctx: discord.Interaction, user: discord.Member, reason: str, duration: str):
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.response.send_message("❌ You need the **Moderate Members** permission.", ephemeral=True)
            return
        if user.top_role >= ctx.user.top_role and ctx.user.id != ctx.guild.owner_id:
            await ctx.response.send_message("❌ You cannot timeout a member with an equal or higher role.", ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.moderate_members:
            await ctx.response.send_message("❌ I don't have permission to timeout members.", ephemeral=True)
            return

        delta = parse_duration(duration)
        if delta is None:
            await ctx.response.send_message("❌ Invalid duration format. Use `1d`, `12h` or `30m`.", ephemeral=True)
            return
        if delta > timedelta(days=28):
            await ctx.response.send_message("❌ Discord limits timeouts to a maximum of **28 days**.", ephemeral=True)
            return

        await user.timeout(delta, reason=f"{ctx.user}: {reason}")

        color = await get_guild_color(ctx.guild_id)
        embed = discord.Embed(title="🔇 Member Timed Out", color=color)
        embed.add_field(name="Member", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.user.mention, inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.response.send_message(embed=embed)

        try:
            dm_embed = discord.Embed(
                title=f"🔇 You were timed out in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Duration:** {duration}",
                color=discord.Color.orange()
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        logger.info(f"Timed out {user} for {duration} in guild {ctx.guild_id} by {ctx.user}")


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))

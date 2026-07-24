import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color, reload_guild_persistent_embeds

logger = logging.getLogger(__name__)

COLOR_TYPES = {
    'global': 'color_primary',
    'welcome': 'color_welcome',
    'level_up': 'color_level_up',
    'success': 'color_success',
    'counting': 'color_counting',
    'verification': 'color_verification',
    'ticket': 'color_ticket',
}

COLOR_DESCRIPTIONS = {
    'global': 'Main color for all bot embeds',
    'welcome': 'Color for welcome messages',
    'level_up': 'Color for level-up notifications',
    'success': 'Color for success/confirmation messages',
    'counting': 'Color for counting game embeds',
    'verification': 'Color for verification messages',
    'ticket': 'Color for ticket panels',
}

# New settings target individual embeds. Legacy group values remain available
# as fallbacks so existing servers do not change appearance unexpectedly.
EMBED_COLOR_CHOICES = [
    app_commands.Choice(name="Welcome message", value="welcome_message"),
    app_commands.Choice(name="Traffic: member joined", value="traffic_join"),
    app_commands.Choice(name="Traffic: member left", value="traffic_leave"),
    app_commands.Choice(name="Traffic: server boost", value="traffic_boost"),
    app_commands.Choice(name="Verification message", value="verification_message"),
    app_commands.Choice(name="Ticket panel", value="ticket_panel"),
    app_commands.Choice(name="Level-up notification", value="level_up_notification"),
    app_commands.Choice(name="Counting message", value="counting_message"),
    app_commands.Choice(name="Message edited log", value="message_edited"),
    app_commands.Choice(name="Message deleted log", value="message_deleted"),
    app_commands.Choice(name="Voice joined log", value="voice_join"),
    app_commands.Choice(name="Voice left log", value="voice_leave"),
    app_commands.Choice(name="Voice switched log", value="voice_switch"),
    app_commands.Choice(name="Global fallback (legacy)", value="global"),
]


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="settings",
        description="Server settings and customization"
    )
    async def settings_group(self, ctx: commands.Context):
        pass

    @settings_group.group(
        name="color",
        description="Customize embed colors"
    )
    async def color_group(self, ctx: commands.Context):
        pass

    @settings_group.group(
        name="prefix",
        description="Customize the bot prefix (Premium)"
    )
    async def prefix_group(self, ctx: commands.Context):
        pass

    async def _has_premium_access(self, user: discord.abc.User) -> bool:
        """Check if the user has premium or is the bot owner."""
        if await self.bot.is_owner(user):
            return True
        tier = await db.get_user_premium_tier(user.id)
        return tier in ("premium", "premium_plus")

    @color_group.command(name="set", description="Set a custom embed color for this server")
    @app_commands.describe(
        hex_color="Hex color code (e.g. #FF5733 or FF5733)",
        type="The individual embed to customize (default: Global fallback)"
    )
    @app_commands.choices(type=EMBED_COLOR_CHOICES)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_set(self, ctx: commands.Context, hex_color: str, type: str = "global"):
        """Set a custom color"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        hex_clean = hex_color.lstrip('#')
        if len(hex_clean) != 6:
            await ctx.send("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return
        try:
            color_int = int(hex_clean, 16)
        except ValueError:
            await ctx.send("❌ Invalid hex color. Use format `#FF5733` or `FF5733`.", ephemeral=True)
            return

        if type in COLOR_TYPES:
            # Backwards-compatible legacy group setting.
            await db.set_guild_color(ctx.guild.id, COLOR_TYPES[type], color_int)
            target_label = f"{type.title()} fallback"
        else:
            await db.set_embed_color(ctx.guild.id, type, color_int)
            target_label = type.replace('_', ' ').title()

        embed = discord.Embed(
            description=f"✅ **{target_label}** color updated!",
            color=discord.Color(color_int)
        )
        embed.add_field(name="Color", value=f"`#{hex_clean.upper()}`")
        if type == "global":
            embed.set_footer(text="This is only the fallback for embeds without an individual color.")
        
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} set embed color {type} to #{hex_clean.upper()}")
        
        # Reload all persistent embeds to apply the new color
        await reload_guild_persistent_embeds(self.bot, ctx.guild.id)

    @color_group.command(name="view", description="View current embed colors for this server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_view(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        colors = await db.get_guild_colors(ctx.guild.id)
        overrides = await db.get_embed_color_overrides(ctx.guild.id)
        defaults = db.DEFAULT_COLORS
        primary_color = await get_guild_color(ctx.guild.id)

        embed = discord.Embed(
            title="🎨 Server Embed Colors",
            description="Each concrete embed can have its own color. Legacy group colors are used only as fallbacks.",
            color=primary_color
        )
        
        for key, col_key in COLOR_TYPES.items():
            val = colors.get(col_key, defaults[col_key])
            is_custom = val != defaults[col_key]
            
            status = ""
            if key != 'global' and not is_custom:
                status = " *(following Global)*"
            elif is_custom:
                status = " *(customized)*"
            else:
                status = " *(customized)*" if val != defaults['color_primary'] else " *(default)*"

            embed.add_field(
                name=f"{key.replace('_', ' ').title()}{status}",
                value=f"`#{val:06X}` - {COLOR_DESCRIPTIONS[key]}",
                inline=False
            )

        if overrides:
            embed.add_field(
                name="Individual overrides",
                value="\n".join(
                    f"**{key.replace('_', ' ').title()}** — `#{value:06X}`"
                    for key, value in sorted(overrides.items())
                ),
                inline=False,
            )
        await ctx.send(embed=embed, ephemeral=True)

    @color_group.command(name="reset", description="Reset all embed colors to defaults")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def color_reset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.reset_guild_colors(ctx.guild.id)
        await db.reset_embed_colors(ctx.guild.id)
        await ctx.send("✅ All embed colors reset to defaults.", ephemeral=True)
        
        # Reload all persistent embeds
        await reload_guild_persistent_embeds(self.bot, ctx.guild.id)

    # ──────────────────────────────────────────────────────
    # /settings prefix set / view / reset  (Premium)
    # ──────────────────────────────────────────────────────

    async def _get_prefix_limit(self, user: discord.abc.User) -> int:
        """Get the maximum number of prefixes a user can set based on their premium tier."""
        if await self.bot.is_owner(user):
            return 5
        tier = await db.get_user_premium_tier(user.id)
        if tier == "premium_plus":
            return 5
        if tier == "premium":
            return 1
        return 0

    @prefix_group.command(name="add", description="Add a custom prefix for this server (Premium)")
    @app_commands.describe(
        prefix="The new prefix (1-10 characters, e.g. '!' or 'mybot.')",
        case_insensitive="Whether the prefix should ignore capitalization (default: False)"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix_add(self, ctx: commands.Context, prefix: str, case_insensitive: bool = False):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        limit = await self._get_prefix_limit(ctx.author)
        if limit == 0:
            await ctx.send(
                "❌ Custom prefixes are a **Premium** feature. Use `/premium info` for upgrade options.",
                ephemeral=True,
            )
            return

        prefix = prefix.strip()
        if not prefix or len(prefix) > 10:
            await ctx.send(
                "❌ Prefix must be between **1** and **10** characters.",
                ephemeral=True,
            )
            return
            
        current_prefixes = await db.get_guild_prefixes(ctx.guild.id)
        
        # Check if it already exists
        if any(p['prefix'].lower() == prefix.lower() if case_insensitive else p['prefix'] == prefix for p in current_prefixes):
            await ctx.send(f"❌ The prefix `{prefix}` is already configured for this server.", ephemeral=True)
            return
            
        if len(current_prefixes) >= limit:
            await ctx.send(
                f"❌ You have reached the maximum of **{limit}** custom prefixes for your Premium tier.",
                ephemeral=True,
            )
            return

        await db.add_guild_prefix(ctx.guild.id, prefix, case_insensitive)

        # Update the in-memory cache so the change takes effect immediately
        import main as _main
        _main._prefix_cache[ctx.guild.id] = await db.get_guild_prefixes(ctx.guild.id)

        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(
            title="✅ Prefix Added",
            description=f"Added `{prefix}` to the server's custom prefixes.",
            color=color,
        )
        embed.add_field(name="Case Insensitive", value="Yes" if case_insensitive else "No", inline=True)
        embed.add_field(name="Example", value=f"`{prefix}warn @user reason`", inline=False)
        embed.set_footer(text="The default prefixes (Atx., atx.) will always work in this server.")
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} added custom prefix '{prefix}' (case_insensitive={case_insensitive})")

    @prefix_group.command(name="remove", description="Remove a custom prefix from this server")
    @app_commands.describe(prefix="The prefix to remove")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix_remove(self, ctx: commands.Context, prefix: str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        current_prefixes = await db.get_guild_prefixes(ctx.guild.id)
        
        # Check if the prefix actually exists (case-sensitive check because it's stored exactly)
        if not any(p['prefix'] == prefix for p in current_prefixes):
            await ctx.send(f"❌ The prefix `{prefix}` is not configured for this server.", ephemeral=True)
            return

        await db.remove_guild_prefix(ctx.guild.id, prefix)

        import main as _main
        _main._prefix_cache[ctx.guild.id] = await db.get_guild_prefixes(ctx.guild.id)

        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(
            title="✅ Prefix Removed",
            description=f"Removed `{prefix}` from the server's custom prefixes.",
            color=color,
        )
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} removed custom prefix '{prefix}'")

    @prefix_group.command(name="view", description="View the current prefixes for this server")
    @commands.guild_only()
    async def prefix_view(self, ctx: commands.Context):
        custom = await db.get_guild_prefixes(ctx.guild.id)
        color = await get_guild_color(ctx.guild.id)

        embed = discord.Embed(title="🔤 Server Prefixes", color=color)
        
        desc = "**Default Prefixes (Always Active):**\n`Atx.`\n`atx.`\n\n"
        
        if custom:
            desc += "**Custom Prefixes:**\n"
            for p in custom:
                ci_text = " *(Case Insensitive)*" if p['case_insensitive'] else ""
                desc += f"• `{p['prefix']}`{ci_text}\n"
        else:
            desc += "**Custom Prefixes:**\n*None configured*"
            
        embed.description = desc
        embed.set_footer(text="You can always use @mention as a prefix too.")
        await ctx.send(embed=embed, ephemeral=True)

    @prefix_group.command(name="reset", description="Remove all custom prefixes")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix_reset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        await db.clear_guild_prefixes(ctx.guild.id)

        # Update the in-memory cache
        import main as _main
        _main._prefix_cache[ctx.guild.id] = []

        color = await get_guild_color(ctx.guild.id)
        embed = discord.Embed(
            title="✅ Prefixes Reset",
            description="All custom prefixes have been removed. The bot will now only respond to the default prefixes (`Atx.`, `atx.`).",
            color=color,
        )
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} reset prefixes to default")


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))


import json
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core import database_pg as db
from cogs.server_management.welcome import WelcomeDashboardView
from utils.embeds import normalize_embed_fields, process_member_text, set_embed_footer


TRIGGER_MAX_LENGTH = 100


def normalize_trigger(value: str) -> str:
    return value.strip().casefold()


def valid_trigger(value: str) -> bool:
    return bool(value) and len(value) <= TRIGGER_MAX_LENGTH and not any(char.isspace() for char in value)


def trigger_matches(content: str, trigger: str) -> bool:
    """Match a trigger as a complete whitespace-delimited token."""
    pattern = rf"(?<!\S){re.escape(trigger)}(?!\S)"
    return re.search(pattern, content.casefold()) is not None


def _json_object(value) -> dict:
    """Normalize JSONB values returned as dicts or JSON strings."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


class TriggerEmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="triggerembed",
        description="Create embeds that are sent when a trigger word is used.",
    )
    @commands.guild_only()
    async def trigger_embed_group(self, ctx: commands.Context):
        pass

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can manage trigger embeds.", ephemeral=True)
            return False
        return True

    async def _open_editor(
        self,
        ctx: commands.Context,
        trigger: str,
    ):
        view = WelcomeDashboardView(self, ctx, trigger_word=trigger)
        await view.fetch_state()
        await ctx.send(
            embed=await view._build_editor_embed(),
            view=view,
            ephemeral=True,
        )
        content, preview_embed = await view._build_preview(ctx, preview_mode=True)
        view.preview_message = await ctx.send(
            content=content or "**Live Preview:**",
            embed=preview_embed,
            ephemeral=True,
        )

    @trigger_embed_group.command(name="create", description="Create a trigger embed with the visual embed builder.")
    @app_commands.describe(trigger="The exact trigger word, for example .partnership")
    @commands.has_permissions(administrator=True)
    async def create_trigger(self, ctx: commands.Context, trigger: str):
        if not await self._require_admin(ctx):
            return

        trigger = normalize_trigger(trigger)
        if not valid_trigger(trigger):
            await ctx.send(
                "❌ The trigger must be one non-empty word without spaces and at most 100 characters.",
                ephemeral=True,
            )
            return

        if await db.get_trigger_embed(ctx.guild.id, trigger):
            await ctx.send(
                f"❌ `{trigger}` already exists. Use `/triggerembed edit` to change it.",
                ephemeral=True,
            )
            return

        await db.create_trigger_embed(
            ctx.guild.id,
            trigger,
            {},
            ctx.author.id,
            content=None,
        )
        await self._open_editor(ctx, trigger)

    @trigger_embed_group.command(name="edit", description="Edit an existing trigger embed with the visual builder.")
    @app_commands.describe(trigger="The trigger word to edit")
    @commands.has_permissions(administrator=True)
    async def edit_trigger(self, ctx: commands.Context, trigger: str):
        if not await self._require_admin(ctx):
            return

        trigger = normalize_trigger(trigger)
        record = await db.get_trigger_embed(ctx.guild.id, trigger)
        if not record:
            await ctx.send(f"❌ No trigger embed exists for `{trigger}`.", ephemeral=True)
            return

        await self._open_editor(ctx, trigger)

    @trigger_embed_group.command(name="list", description="List all trigger embeds in this server.")
    @commands.has_permissions(administrator=True)
    async def list_triggers(self, ctx: commands.Context):
        if not await self._require_admin(ctx):
            return

        records = await db.get_trigger_embeds(ctx.guild.id)
        if not records:
            await ctx.send("ℹ️ No trigger embeds are configured.", ephemeral=True)
            return

        lines = [f"• `{record['trigger_word']}`" for record in records]
        await ctx.send(
            "**Configured trigger embeds:**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @trigger_embed_group.command(name="delete", description="Delete a trigger embed.")
    @app_commands.describe(trigger="The trigger word to delete")
    @commands.has_permissions(administrator=True)
    async def delete_trigger(self, ctx: commands.Context, trigger: str):
        if not await self._require_admin(ctx):
            return

        trigger = normalize_trigger(trigger)
        if not await db.delete_trigger_embed(ctx.guild.id, trigger):
            await ctx.send(f"❌ No trigger embed exists for `{trigger}`.", ephemeral=True)
            return

        await ctx.send(f"✅ Trigger embed `{trigger}` was deleted.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot or not message.content:
            return

        try:
            records = await db.get_trigger_embeds(message.guild.id)
            for record in records:
                if not trigger_matches(message.content, record["trigger_word"]):
                    continue

                embed_data = _json_object(record.get("embed_data"))
                embed_enabled = bool(embed_data.get("enabled", True))
                embed = discord.Embed.from_dict(embed_data) if embed_enabled else None
                event_time = discord.utils.utcnow()
                extra_values = {"trigger": record["trigger_word"], "event": "trigger"}

                def render(value: Optional[str], footer: bool = False) -> Optional[str]:
                    if not value:
                        return None
                    return process_member_text(
                        value,
                        message.author,
                        event_time=event_time,
                        time_value="" if footer else None,
                        extra_values=extra_values,
                    ) or None

                if embed is not None:
                    embed.title = render(embed_data.get("title"))
                    embed.description = render(embed_data.get("description"))
                    if embed_data.get("author"):
                        embed.set_author(
                            name=render(embed_data["author"].get("name")) or " ",
                            icon_url=render(embed_data["author"].get("icon_url")),
                        )
                    footer = embed_data.get("footer") or {}
                    set_embed_footer(
                        embed,
                        text=render(footer.get("text"), footer=True),
                        icon_url=render(footer.get("icon_url")),
                    )
                    embed.clear_fields()
                    for field in normalize_embed_fields(embed_data.get("fields")):
                        embed.add_field(
                            name=render(field.get("name")) or "Field",
                            value=(render(field.get("value")) or "-")[:1024],
                            inline=bool(field.get("inline", False)),
                        )
                    if embed_data.get("timestamp"):
                        embed.timestamp = event_time

                content = process_member_text(
                    record.get("content"),
                    message.author,
                    event_time=event_time,
                    extra_values=extra_values,
                ) or None
                if not embed and not content:
                    continue
                await message.channel.send(content=content, embed=embed)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass
        except Exception:
            self.bot.dispatch("trigger_embed_error", message)


async def setup(bot: commands.Bot):
    await bot.add_cog(TriggerEmbedCog(bot))

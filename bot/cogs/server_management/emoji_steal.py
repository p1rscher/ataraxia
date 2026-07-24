import asyncio
import io
import logging
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


logger = logging.getLogger(__name__)

EMOJI_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,32}$")
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:[A-Za-z0-9_]{2,32}:[0-9]+>")
MESSAGE_FETCH_TIMEOUT = 10
EXPRESSION_COPY_TIMEOUT = 30
MAX_STICKER_SIZE = 512 * 1024


class StealCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _finish_deferred(ctx: commands.Context, content: str):
        """Replace the deferred slash response instead of leaving it thinking."""
        if ctx.interaction:
            await ctx.interaction.edit_original_response(content=content)
        else:
            await ctx.send(content)

    @commands.hybrid_command(
        name="steal",
        aliases=["stealemoji", "steal-emoji"],
        description="Copy a custom emoji or sticker to this server.",
    )
    @app_commands.describe(
        message_id="ID of the message containing the custom emoji or sticker",
        name="Optional new name for the emoji or sticker",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def steal_emoji(
        self,
        ctx: commands.Context,
        message_id: str,
        name: Optional[str] = None,
    ):
        """Copy the custom emoji or sticker from a message in the current channel."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        try:
            parsed_message_id = int(message_id.strip())
        except ValueError:
            await ctx.send(
                "❌ Please provide a valid message ID.",
                ephemeral=True,
            )
            return

        bot_member = guild.me
        bot_permissions = bot_member.guild_permissions if bot_member else None
        if not bot_permissions or not (
            bot_permissions.create_expressions or bot_permissions.manage_expressions
        ):
            await ctx.send(
                "❌ I need the **Create Expressions** or **Manage Expressions** permission "
                "to add emojis to this server.",
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=True)

        try:
            async with asyncio.timeout(MESSAGE_FETCH_TIMEOUT):
                message = await ctx.channel.fetch_message(parsed_message_id)
        except TimeoutError:
            await self._finish_deferred(
                ctx,
                "❌ Discord took too long to load the message. Please try again.",
            )
            return
        except discord.NotFound:
            await self._finish_deferred(
                ctx,
                "❌ I could not find that message in this channel.",
            )
            return
        except discord.Forbidden:
            await self._finish_deferred(
                ctx,
                "❌ I do not have permission to read that message.",
            )
            return
        except (discord.HTTPException, AttributeError):
            await self._finish_deferred(
                ctx,
                "❌ The message could not be loaded. Run the command in the same channel "
                "as the message.",
            )
            return

        emoji_values = list(dict.fromkeys(CUSTOM_EMOJI_PATTERN.findall(message.content)))
        stickers = message.stickers
        expression_count = len(emoji_values) + len(stickers)

        if expression_count == 0:
            await self._finish_deferred(
                ctx,
                "❌ That message does not contain a custom Discord emoji or sticker.",
            )
            return
        if expression_count > 1:
            await self._finish_deferred(
                ctx,
                "❌ That message contains multiple emojis or stickers. Please use a message "
                "containing exactly one item to copy.",
            )
            return

        if stickers:
            await self._copy_sticker(ctx, guild, stickers[0], name)
            return

        # Passing ``client=`` is only supported by newer discord.py versions.
        # Downloading through the bot's HTTP client keeps this compatible with
        # older deployments while still reusing Discord's existing session.
        partial_emoji = discord.PartialEmoji.from_str(emoji_values[0])
        emoji_name = name.strip() if name else partial_emoji.name
        if not emoji_name or not EMOJI_NAME_PATTERN.fullmatch(emoji_name):
            await self._finish_deferred(
                ctx,
                "❌ The emoji name must be 2–32 characters long and may only contain "
                "letters, numbers, and underscores.",
            )
            return

        try:
            async with asyncio.timeout(EXPRESSION_COPY_TIMEOUT):
                image = await self.bot.http.get_from_cdn(str(partial_emoji.url))
                created_emoji = await guild.create_custom_emoji(
                    name=emoji_name,
                    image=image,
                    reason=f"Emoji copied by {ctx.author} ({ctx.author.id})",
                )
        except TimeoutError:
            logger.warning(
                "Timed out while copying emoji %s to guild %s",
                partial_emoji.id,
                guild.id,
            )
            await self._finish_deferred(
                ctx,
                "❌ Discord took too long to copy the emoji. Please try again.",
            )
            return
        except discord.NotFound:
            await self._finish_deferred(
                ctx,
                "❌ The source emoji no longer exists or could not be downloaded.",
            )
            return
        except discord.Forbidden:
            await self._finish_deferred(
                ctx,
                "❌ Discord denied the request. Please check my server permissions.",
            )
            return
        except discord.HTTPException as error:
            logger.warning(
                "Failed to copy emoji %s to guild %s: %s",
                partial_emoji.id,
                guild.id,
                error,
            )
            await self._finish_deferred(
                ctx,
                "❌ Discord could not add the emoji. The server's emoji slots may be full.",
            )
            return

        logger.info(
            "Emoji %s (%s) copied to guild %s by user %s",
            created_emoji.name,
            created_emoji.id,
            guild.id,
            ctx.author.id,
        )
        await self._finish_deferred(
            ctx,
            f"✅ Successfully added {created_emoji} as `:{created_emoji.name}:`.",
        )

    async def _copy_sticker(
        self,
        ctx: commands.Context,
        guild: discord.Guild,
        sticker_item: discord.StickerItem,
        name: Optional[str],
    ):
        sticker_name = name.strip() if name else sticker_item.name
        if not 2 <= len(sticker_name) <= 30:
            await self._finish_deferred(
                ctx,
                "❌ The sticker name must be 2–30 characters long.",
            )
            return

        try:
            async with asyncio.timeout(EXPRESSION_COPY_TIMEOUT):
                source_sticker = await sticker_item.fetch()
                image = await self.bot.http.get_from_cdn(str(sticker_item.url))

                if len(image) > MAX_STICKER_SIZE:
                    await self._finish_deferred(
                        ctx,
                        "❌ The sticker is larger than Discord's 512 KiB upload limit.",
                    )
                    return

                description = (source_sticker.description or "")[:100]
                if len(description) == 1:
                    description = ""

                sticker_emoji = getattr(source_sticker, "emoji", None)
                if not sticker_emoji:
                    tags = getattr(source_sticker, "tags", [])
                    sticker_emoji = tags[0] if tags else "🙂"

                extension = sticker_item.format.file_extension
                sticker_file = discord.File(
                    io.BytesIO(image),
                    filename=f"sticker.{extension}",
                )
                try:
                    created_sticker = await guild.create_sticker(
                        name=sticker_name,
                        description=description,
                        emoji=sticker_emoji,
                        file=sticker_file,
                        reason=f"Sticker copied by {ctx.author} ({ctx.author.id})",
                    )
                finally:
                    sticker_file.close()
        except TimeoutError:
            logger.warning(
                "Timed out while copying sticker %s to guild %s",
                sticker_item.id,
                guild.id,
            )
            await self._finish_deferred(
                ctx,
                "❌ Discord took too long to copy the sticker. Please try again.",
            )
            return
        except discord.NotFound:
            await self._finish_deferred(
                ctx,
                "❌ The source sticker no longer exists or could not be downloaded.",
            )
            return
        except discord.Forbidden:
            await self._finish_deferred(
                ctx,
                "❌ Discord denied the request. Please check my server permissions.",
            )
            return
        except (discord.HTTPException, TypeError) as error:
            logger.warning(
                "Failed to copy sticker %s to guild %s: %s",
                sticker_item.id,
                guild.id,
                error,
            )
            await self._finish_deferred(
                ctx,
                "❌ Discord could not add the sticker. Its format may be unsupported or "
                "the server's sticker slots may be full.",
            )
            return

        logger.info(
            "Sticker %s (%s) copied to guild %s by user %s",
            created_sticker.name,
            created_sticker.id,
            guild.id,
            ctx.author.id,
        )
        await self._finish_deferred(
            ctx,
            f"✅ Successfully added the sticker **{created_sticker.name}**.",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StealCog(bot))
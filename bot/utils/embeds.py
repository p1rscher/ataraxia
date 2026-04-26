# utils/embeds.py
import discord
import datetime
import asyncio
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)


async def get_guild_color(guild_id: int, color_type: str = 'color_primary') -> discord.Color:
    """Fetches the guild's embed color for the given type with fallback to primary."""
    if guild_id is None:
        return discord.Color(5793266)
    
    colors = await db.get_guild_colors(guild_id)
    defaults = db.DEFAULT_COLORS
    
    # 1. If requested color is customized, use it
    current_val = colors.get(color_type, defaults.get(color_type, 5793266))
    if current_val != defaults.get(color_type):
        return discord.Color(current_val)
        
    # 2. If primary color is customized, use it as fallback
    primary_val = colors.get('color_primary', defaults['color_primary'])
    if primary_val != defaults['color_primary']:
        return discord.Color(primary_val)
        
    # 3. Otherwise use the default for the requested type
    return discord.Color(current_val)


async def reload_guild_persistent_embeds(bot: discord.Client, guild_id: int):
    """Refreshes the color of all persistent embeds in the guild."""
    guild = bot.get_guild(guild_id)
    if not guild:
        return

    # 1. Reaction Roles
    panels = await db.get_reaction_role_messages(guild_id)
    for p in panels:
        if p['message_id'] <= 0: # Skip drafts
            continue
        try:
            channel = guild.get_channel(p['channel_id'])
            if channel:
                msg = await channel.fetch_message(p['message_id'])
                if msg.embeds:
                    embed = msg.embeds[0]
                    embed.color = await get_guild_color(guild_id)
                    await msg.edit(embed=embed)
        except discord.NotFound:
            await db.delete_reaction_role_message(p['message_id'])
        except Exception as e:
            logger.error(f"Failed to reload reaction role panel {p['message_id']}: {e}")

    # 2. Verification
    verif = await db.get_verification(guild_id)
    if verif:
        msg_id, channel_id, _ = verif
        if msg_id and msg_id > 0:
            try:
                channel = guild.get_channel(channel_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    if msg.embeds:
                        embed = msg.embeds[0]
                        embed.color = await get_guild_color(guild_id, 'color_verification')
                        await msg.edit(embed=embed)
            except discord.NotFound:
                # Optional: clear message_id from verification settings but keep role_id?
                pass 
            except Exception as e:
                logger.error(f"Failed to reload verification message for guild {guild_id}: {e}")

    # 3. Temp Voice Control
    tv_panel = await db.get_temp_voice_control_channel(guild_id)
    if tv_panel:
        channel_id, msg_id = tv_panel
        if msg_id > 0:
            try:
                channel = guild.get_channel(channel_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    if msg.embeds:
                        embed = msg.embeds[0]
                        embed.color = await get_guild_color(guild_id)
                        await msg.edit(embed=embed)
            except discord.NotFound:
                # Maybe remove from DB?
                pass
            except Exception as e:
                logger.error(f"Failed to reload temp voice panel for guild {guild_id}: {e}")

    # 4. Ticket Panels
    t_panels = await db.get_ticket_panels(guild_id)
    for tp in t_panels:
        if tp['message_id'] <= 0:
            continue
        try:
            channel = guild.get_channel(tp['channel_id'])
            if channel:
                msg = await channel.fetch_message(tp['message_id'])
                if msg.embeds:
                    embed = msg.embeds[0]
                    embed.color = await get_guild_color(guild_id, 'color_ticket')
                    await msg.edit(embed=embed)
        except discord.NotFound:
            await db.remove_ticket_panel(tp['message_id'])
        except Exception as e:
            logger.error(f"Failed to reload ticket panel {tp['message_id']}: {e}")


async def make_edit_embed(before: discord.Message, diff_text: str) -> discord.Embed:

    # if diff_text is a coroutine, await it
    if asyncio.iscoroutine(diff_text):
        diff_text = await diff_text


    embed = discord.Embed(
        title="Message Edited",
        description=f"Message from **{before.author.display_name}** was edited.",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    # Metadata
    embed.add_field(name="Guild", value=before.guild.name if before.guild else "DM", inline=True)
    embed.add_field(name="Channel", value=f"{before.channel.mention}" if getattr(before.channel, "name", None) else str(before.channel.id), inline=True)
    embed.add_field(name="Author ID", value=f"<@{before.author.id}>", inline=True)

    embed = await make_parts(diff_text, "Edited", embed)

    # Link to message
    try:
        if before.guild and before.id:
            embed.add_field(name="Message Link", value=f"[Message Link](https://discord.com/channels/{before.guild.id}/{before.channel.id}/{before.id})", inline=False)
    except Exception:
        pass

    return embed


async def make_edit_embed_from_db(message_row, diff_text: str, bot: discord.Client) -> discord.Embed:
    # message_row = (message_id, guild_id, channel_id, author_id, content, created_at)
    msg_id, guild_id, channel_id, author_id, content, created_at, edited_at, deleted_at, current_version = message_row
    
    embed = discord.Embed(
        title="Message Edited",
        description=f"Message from **{discord.utils.get(bot.get_all_members(), id=author_id).display_name}** was edited.",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    embed.add_field(name="Message ID", value=str(msg_id), inline=True)
    embed.add_field(name="Author", value=f"<@{author_id}>", inline=True)
    embed.add_field(name="Channel", value=f"<#{channel_id}>", inline=True)
    
    embed = await make_parts(diff_text, "Edited", embed)
    
    try:
        if guild_id and msg_id:
            embed.add_field(name="Message Link", value=f"[Message Link](https://discord.com/channels/{guild_id}/{channel_id}/{msg_id})", inline=False)
    except Exception:
        pass

    return embed


async def make_delete_embed(message, channel_mention) -> discord.Embed:

    deleted_text = message.content if isinstance(message, discord.Message) else message[4]

    embed = discord.Embed(
        title="Message Deleted",
        description=f"In {channel_mention} a message was deleted.",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    # Metadata
    embed.add_field(name="Guild", value=message.guild.name if message.guild else "DM", inline=True)
    embed.add_field(name="Channel", value=f"{channel_mention}" if getattr(message.channel, "name", None) else str(message.channel.id), inline=True)
    embed.add_field(name="Author", value=str(f'<@{message.author.id}>'), inline=True)

    return await make_parts(deleted_text, "Deleted", embed)


# Extra function for data from DB rows
async def make_delete_embed_from_db(message_row, channel_mention: str) -> discord.Embed:
    # message_row = (message_id, guild_id, channel_id, author_id, content, created_at)
    msg_id, guild_id, channel_id, author_id, content, created_at, edited_at, deleted_at, current_version = message_row
    
    embed = discord.Embed(
        title="Message Deleted",
        description=f"In {channel_mention} a message was deleted.",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    embed.add_field(name="Message ID", value=str(msg_id), inline=True)
    if author_id:
        embed.add_field(name="Author", value=f"<@{author_id}>", inline=True)
    
    return await make_parts(content, "Deleted", embed)


async def make_parts(text: str, field_name: str, embed: discord.Embed):
    MAX_FIELD_LENGTH = 1024
    CHUNK_SIZE = MAX_FIELD_LENGTH - 10  # some buffer
    total_parts = (len(text) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for i in range(total_parts):
        start = i * CHUNK_SIZE
        end = start + CHUNK_SIZE
        part = text[start:end]
        if i+1 < total_parts:
            part = part + "..."
        if i > 0:
            part = "..." + part
        embed.add_field(name=f"{field_name} (part {i+1}/{total_parts})", value=part or "​", inline=False)

    return embed

# utils/embeds.py
import discord
import datetime
import asyncio


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

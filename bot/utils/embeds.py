# utils/embeds.py
import discord
import datetime
import asyncio
import json
import logging
from typing import Optional
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


async def get_embed_color(
    guild_id: int,
    embed_key: str,
    fallback_type: str = 'color_primary',
) -> discord.Color:
    """Get the color for one concrete embed with legacy fallback support."""
    override = await db.get_embed_color_override(guild_id, embed_key)
    if override is not None:
        return discord.Color(override)
    return await get_guild_color(guild_id, fallback_type)


def ordinal(number: Optional[int]) -> str:
    """Format a member count as an English ordinal (31st, 22nd, 13th)."""
    if number is None:
        return "Unknown"
    number = int(number)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def human_member_count(guild: discord.Guild) -> int:
    """Count cached human members without counting bots."""
    return sum(1 for member in guild.members if not member.bot)


def member_template_values(
    member: discord.Member,
    *,
    event_time: Optional[datetime.datetime] = None,
    extra_values: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Return values for member-message placeholders."""
    event_time = event_time or discord.utils.utcnow()
    count = human_member_count(member.guild)
    values = {
        "{user}": member.mention,
        "{user.name}": str(member),
        "{user.avatar}": member.display_avatar.url,
        "{server}": member.guild.name,
        "{server.icon}": member.guild.icon.url if member.guild.icon else "",
        "{member_count}": str(count),
        "{member_count_ext}": ordinal(count),
        "{time}": f"<t:{int(event_time.timestamp())}:F>",
    }
    if extra_values:
        values.update({f"{{{key}}}": str(value) for key, value in extra_values.items()})
    return values


def has_time_placeholder(*values: Optional[str]) -> bool:
    """Return whether any embed value explicitly requests the send time."""
    return any(isinstance(value, str) and "{time}" in value for value in values)


def process_member_text(
    text: Optional[str],
    member: discord.Member,
    *,
    event_time: Optional[datetime.datetime] = None,
    time_value: Optional[str] = None,
    extra_values: Optional[dict[str, str]] = None,
) -> str:
    """Replace supported member-message placeholders in a text value."""
    if not text:
        return ""
    values = member_template_values(
        member,
        event_time=event_time,
        extra_values=extra_values,
    )
    if time_value is not None:
        values["{time}"] = time_value
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    return text


async def send_member_traffic_embed(
    member: discord.Member,
    event: str,
    *,
    timestamp: Optional[datetime.datetime] = None,
) -> bool:
    """Send a join, leave, or boost embed to the shared traffic-log channel."""
    if event not in {'join', 'leave', 'boost'}:
        raise ValueError(f"Unsupported traffic event: {event}")

    # ``None`` means use the shared legacy traffic channel, while ``0`` means
    # this event was explicitly disabled by an administrator.
    event_channel_id = await db.get_traffic_event_channel_id(member.guild.id, event)
    if event_channel_id == 0:
        return False
    channel_id = event_channel_id or await db.get_traffic_log_channel_id(member.guild.id)
    if not channel_id:
        return False

    channel = member.guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return False

    now = timestamp or discord.utils.utcnow()
    config = await db.get_traffic_embed_config(member.guild.id, event) or {}

    if event == 'join':
        default_title = "{user.name} joined the server"
        default_fields = [
            {"name": "User", "value": "{user}", "inline": True},
            {"name": "Account creation", "value": "{account_created}", "inline": True},
            {"name": "Member count", "value": "{member_count}", "inline": True},
        ]
    elif event == 'leave':
        default_title = "{user.name} left the server"
        default_fields = [
            {"name": "User", "value": "{user}", "inline": True},
            {"name": "Joined date", "value": "{joined_at}", "inline": True},
            {"name": "Member count", "value": "{member_count}", "inline": True},
        ]
    else:
        default_title = "{user.name} boosted the server"
        default_fields = [
            {"name": "User", "value": "{user}", "inline": True},
            {"name": "Member count", "value": "{member_count}", "inline": True},
        ]

    default_config = {
        'title': default_title,
        'description': None,
        'author_name': None,
        'author_icon': None,
        'footer_text': "{server} • {member_count} members",
        'footer_icon': "{server.icon}",
        'thumbnail': "{user.avatar}",
        'image': None,
        'fields': default_fields,
        'timestamp_enabled': True,
    }
    default_config.update(config)
    raw_fields = default_config.get('fields') or default_fields
    if isinstance(raw_fields, str):
        try:
            raw_fields = json.loads(raw_fields)
        except (TypeError, json.JSONDecodeError):
            raw_fields = []

    extra_values = {
        'account_created': f"<t:{int(member.created_at.timestamp())}:f> (<t:{int(member.created_at.timestamp())}:R>)",
        'joined_at': (
            f"<t:{int(member.joined_at.timestamp())}:f> (<t:{int(member.joined_at.timestamp())}:R>)"
            if member.joined_at else "Unknown"
        ),
        'event': event,
    }

    def render(value):
        if not value:
            return None
        return process_member_text(
            value,
            member,
            event_time=now,
            extra_values=extra_values,
        ) or None

    footer_text = default_config.get('footer_text')
    render_footer = lambda value: process_member_text(
        value,
        member,
        event_time=now,
        time_value="",
        extra_values=extra_values,
    ) or None

    embed = discord.Embed(
        title=render(default_config.get('title')),
        description=render(default_config.get('description')),
        color=await get_embed_color(member.guild.id, f'traffic_{event}'),
        timestamp=(
            now
            if default_config.get('timestamp_enabled', True) or '{time}' in (footer_text or '')
            else None
        ),
    )
    if default_config.get('author_name'):
        embed.set_author(
            name=render(default_config['author_name']) or " ",
            icon_url=render(default_config.get('author_icon')),
        )
    if default_config.get('thumbnail'):
        embed.set_thumbnail(url=render(default_config['thumbnail']))
    if default_config.get('image'):
        embed.set_image(url=render(default_config['image']))
    if default_config.get('footer_text'):
        embed.set_footer(
            text=render_footer(default_config['footer_text']) or " ",
            icon_url=render(default_config.get('footer_icon')),
        )
    for field in raw_fields[:25]:
        if not isinstance(field, dict) or not field.get('name'):
            continue
        embed.add_field(
            name=render(field['name']) or "Field",
            value=(render(field.get('value')) or "-")[:1024],
            inline=bool(field.get('inline', False)),
        )

    await channel.send(embed=embed)
    return True


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
        color=await get_embed_color(before.guild.id, 'message_edited') if before.guild else discord.Color.orange(),
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
        color=await get_embed_color(guild_id, 'message_edited') if guild_id else discord.Color.orange(),
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
        color=await get_embed_color(message.guild.id, 'message_deleted') if message.guild else discord.Color.red(),
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
        color=await get_embed_color(guild_id, 'message_deleted') if guild_id else discord.Color.red(),
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

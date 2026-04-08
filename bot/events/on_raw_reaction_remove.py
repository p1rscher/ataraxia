import logging
from typing import Optional

import discord

from core import database_pg as db

bot: Optional[discord.Client] = None
logger = logging.getLogger(__name__)


async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if bot is None or bot.user is None:
        return
    if not payload.guild_id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    entry = await db.get_reaction_role_entry(payload.message_id, str(payload.emoji))
    if not entry:
        return

    role = guild.get_role(entry['role_id'])
    if role is None:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

    try:
        await member.remove_roles(role, reason="Reaction role removed")
    except Exception as exc:
        logger.error(f"Failed to remove reaction role {role.id} from {member}: {exc}")

"""Request bodies. Discord IDs travel as strings: they do not fit into a JavaScript number."""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def _snowflake(value):
    if isinstance(value, str) and value.isdigit() and 15 <= len(value) <= 20:
        return int(value)
    raise ValueError("must be a Discord ID given as a string of digits")


Snowflake = Annotated[int, BeforeValidator(_snowflake)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class XPSettings(Strict):
    message_cooldown: int = Field(ge=0, le=3600)
    voice_interval: int = Field(ge=60, le=3600)
    message_xp_min: int = Field(ge=1, le=1000)
    message_xp_max: int = Field(ge=1, le=1000)
    voice_xp_min: int = Field(ge=1, le=1000)
    voice_xp_max: int = Field(ge=1, le=1000)

    @model_validator(mode="after")
    def _ranges(self):
        if self.message_xp_min > self.message_xp_max:
            raise ValueError("message_xp_min must not be greater than message_xp_max")
        if self.voice_xp_min > self.voice_xp_max:
            raise ValueError("voice_xp_min must not be greater than voice_xp_max")
        return self


class VoiceRequirements(Strict):
    require_non_afk: bool
    require_non_deaf: bool
    require_non_muted: bool
    require_others_in_channel: bool


class Multiplier(Strict):
    multiplier: float = Field(ge=0, le=10)


class LogChannels(Strict):
    """Only the fields that are sent are changed; null clears a channel."""
    message: Optional[Snowflake] = None
    say: Optional[Snowflake] = None
    level: Optional[Snowflake] = None
    voice: Optional[Snowflake] = None
    mod: Optional[Snowflake] = None
    traffic: Optional[Snowflake] = None
    ticket: Optional[Snowflake] = None
    # Level-up announcements can also be switched off entirely.
    level_disabled: Optional[bool] = None


class LevelRole(Strict):
    role_id: Snowflake


class AutoRoles(Strict):
    enabled: bool
    user_role_ids: list[Snowflake] = Field(max_length=25)
    bot_role_ids: list[Snowflake] = Field(max_length=25)

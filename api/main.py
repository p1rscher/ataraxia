# api/main.py
"""
Ataraxia Bot - REST API
Provides endpoints for the web dashboard
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from contextlib import asynccontextmanager
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

from core import database_pg as db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init_db()
    yield
    # Shutdown
    await db.close_db()

app = FastAPI(
    title="Ataraxia Bot API",
    description="REST API for Ataraxia Discord Bot Dashboard",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS (Request/Response Schemas) ====================

class XPSettings(BaseModel):
    message_cooldown: int
    voice_interval: int
    message_xp_min: int
    message_xp_max: int
    voice_xp_min: int
    voice_xp_max: int

class UpdateCooldown(BaseModel):
    cooldown: int
    voice_interval: Optional[int] = None

class UpdateVoiceInterval(BaseModel):
    interval: int

class UpdateMessageXP(BaseModel):
    min_xp: int
    max_xp: int

class UpdateVoiceXP(BaseModel):
    min_xp: int
    max_xp: int

class UpdateAllXPSettings(BaseModel):
    message_xp_min: int
    message_xp_max: int
    voice_xp_min: int
    voice_xp_max: int
    message_cooldown: Optional[int] = None
    voice_interval: Optional[int] = None

class ChannelMultiplier(BaseModel):
    channel_id: int
    multiplier: float

class RoleMultiplier(BaseModel):
    role_id: int
    multiplier: float

class LogChannel(BaseModel):
    channel_id: int

class VoiceXPRequirements(BaseModel):
    require_non_afk: bool
    require_non_deaf: bool
    require_non_muted: bool
    require_others_in_channel: bool

class VoiceXPRequirementUpdate(BaseModel):
    requirement: str
    value: bool

class LevelRole(BaseModel):
    level: int
    role_id: int

class AutoRole(BaseModel):
    role_id: int

class ParentRole(BaseModel):
    parent_role_id: int
    child_role_ids: Optional[List[int]] = None

class ChildRole(BaseModel):
    child_role_id: int

class Verification(BaseModel):
    message_id: int
    channel_id: int
    role_id: int

# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    """API Health Check"""
    return {"status": "online", "message": "Ataraxia Bot API"}

@app.get("/health")
async def health():
    """Detailed health check"""
    return {"status": "healthy", "database": "connected"}

# ==================== XP SETTINGS ====================

@app.get("/api/guilds/{guild_id}/xp/settings", response_model=XPSettings)
async def get_xp_settings(guild_id: int):
    """
    Get all XP settings for a guild
    
    - **guild_id**: Discord Guild ID
    """
    settings = await db.get_all_xp_settings(guild_id)
    return settings

@app.put("/api/guilds/{guild_id}/xp/settings")
async def update_all_xp_settings(guild_id: int, data: UpdateAllXPSettings):
    """
    Update all XP settings at once
    
    - **guild_id**: Discord Guild ID
    - **message_xp_min**: Minimum message XP (1-1000)
    - **message_xp_max**: Maximum message XP (1-1000)
    - **voice_xp_min**: Minimum voice XP (1-1000)
    - **voice_xp_max**: Maximum voice XP (1-1000)
    - **message_cooldown**: Message cooldown in seconds (optional, 0-3600)
    - **voice_interval**: Voice interval in seconds (optional, 60-3600)
    """
    # Validate XP ranges
    if data.message_xp_min < 1 or data.message_xp_max < 1 or data.message_xp_max > 1000:
        raise HTTPException(status_code=400, detail="Invalid message XP range")
    if data.message_xp_min > data.message_xp_max:
        raise HTTPException(status_code=400, detail="Message min XP cannot be greater than max XP")
    
    if data.voice_xp_min < 1 or data.voice_xp_max < 1 or data.voice_xp_max > 1000:
        raise HTTPException(status_code=400, detail="Invalid voice XP range")
    if data.voice_xp_min > data.voice_xp_max:
        raise HTTPException(status_code=400, detail="Voice min XP cannot be greater than max XP")
    
    # Update XP ranges
    await db.set_message_xp_range(guild_id, data.message_xp_min, data.message_xp_max)
    await db.set_voice_xp_range(guild_id, data.voice_xp_min, data.voice_xp_max)
    
    # Update cooldowns if provided
    if data.message_cooldown is not None:
        if data.message_cooldown < 0 or data.message_cooldown > 3600:
            raise HTTPException(status_code=400, detail="Message cooldown must be between 0 and 3600 seconds")
        await db.set_xp_cooldown(guild_id, data.message_cooldown)
    
    if data.voice_interval is not None:
        if data.voice_interval < 60 or data.voice_interval > 3600:
            raise HTTPException(status_code=400, detail="Voice interval must be between 60 and 3600 seconds")
        await db.set_voice_xp_interval(guild_id, data.voice_interval)
    
    # Return updated settings
    updated_settings = await db.get_all_xp_settings(guild_id)
    return {"success": True, "settings": updated_settings}

@app.put("/api/guilds/{guild_id}/xp/cooldown")
async def update_xp_cooldown(guild_id: int, data: UpdateCooldown):
    """
    Update message XP cooldown and voice XP interval
    
    - **guild_id**: Discord Guild ID
    - **cooldown**: Message cooldown in seconds (0-3600)
    - **voice_interval**: Voice interval in seconds (optional, 60-3600)
    """
    if data.cooldown < 0 or data.cooldown > 3600:
        raise HTTPException(status_code=400, detail="Cooldown must be between 0 and 3600 seconds")
    
    await db.set_xp_cooldown(guild_id, data.cooldown)
    
    # If voice_interval is also provided, update it
    if hasattr(data, 'voice_interval') and data.voice_interval is not None:
        if data.voice_interval < 60 or data.voice_interval > 3600:
            raise HTTPException(status_code=400, detail="Voice interval must be between 60 and 3600 seconds")
        await db.set_voice_xp_interval(guild_id, data.voice_interval)
        return {"success": True, "message_cooldown": data.cooldown, "voice_interval": data.voice_interval}
    
    return {"success": True, "cooldown": data.cooldown}

@app.put("/api/guilds/{guild_id}/xp/voice-interval")
async def update_voice_interval(guild_id: int, data: UpdateVoiceInterval):
    """
    Update voice XP interval
    
    - **guild_id**: Discord Guild ID
    - **interval**: Interval in seconds (60-3600)
    """
    if data.interval < 60 or data.interval > 3600:
        raise HTTPException(status_code=400, detail="Interval must be between 60 and 3600 seconds")
    
    await db.set_voice_xp_interval(guild_id, data.interval)
    return {"success": True, "interval": data.interval}

@app.put("/api/guilds/{guild_id}/xp/message-xp")
async def update_message_xp(guild_id: int, data: UpdateMessageXP):
    """
    Update message XP range
    
    - **guild_id**: Discord Guild ID
    - **min_xp**: Minimum XP (1-1000)
    - **max_xp**: Maximum XP (1-1000)
    """
    if data.min_xp < 1 or data.max_xp < 1 or data.max_xp > 1000:
        raise HTTPException(status_code=400, detail="Invalid XP range")
    if data.min_xp > data.max_xp:
        raise HTTPException(status_code=400, detail="Min XP cannot be greater than max XP")
    
    await db.set_message_xp_range(guild_id, data.min_xp, data.max_xp)
    return {"success": True, "min_xp": data.min_xp, "max_xp": data.max_xp}

# Alternative path for message XP
@app.put("/api/guilds/{guild_id}/xp/messagexp")
async def update_message_xp_alt(guild_id: int, data: UpdateMessageXP):
    """Update message XP range (alternative path)"""
    return await update_message_xp(guild_id, data)

@app.put("/api/guilds/{guild_id}/xp/voice-xp")
async def update_voice_xp(guild_id: int, data: UpdateVoiceXP):
    """
    Update voice XP range
    
    - **guild_id**: Discord Guild ID
    - **min_xp**: Minimum XP (1-1000)
    - **max_xp**: Maximum XP (1-1000)
    """
    if data.min_xp < 1 or data.max_xp < 1 or data.max_xp > 1000:
        raise HTTPException(status_code=400, detail="Invalid XP range")
    if data.min_xp > data.max_xp:
        raise HTTPException(status_code=400, detail="Min XP cannot be greater than max XP")
    
    await db.set_voice_xp_range(guild_id, data.min_xp, data.max_xp)
    return {"success": True, "min_xp": data.min_xp, "max_xp": data.max_xp}

# Alternative path for voice XP
@app.put("/api/guilds/{guild_id}/xp/voicexp")
async def update_voice_xp_alt(guild_id: int, data: UpdateVoiceXP):
    """Update voice XP range (alternative path)"""
    return await update_voice_xp(guild_id, data)

# ==================== MULTIPLIERS ====================

@app.get("/api/guilds/{guild_id}/multipliers")
async def get_all_multipliers(guild_id: int):
    """
    Get all multipliers (channels and roles) for a guild
    
    - **guild_id**: Discord Guild ID
    """
    channel_multipliers = await db.get_all_channel_multipliers(guild_id)
    role_multipliers = await db.get_all_role_multipliers(guild_id)
    
    return {
        "channel_multipliers": [{"channel_id": ch_id, "multiplier": mult} for ch_id, mult in channel_multipliers],
        "role_multipliers": [{"role_id": role_id, "multiplier": mult} for role_id, mult in role_multipliers]
    }

@app.get("/api/guilds/{guild_id}/multipliers/channels")
async def get_channel_multipliers(guild_id: int):
    """
    Get all channel multipliers for a guild
    
    - **guild_id**: Discord Guild ID
    """
    multipliers = await db.get_all_channel_multipliers(guild_id)
    return [{"channel_id": ch_id, "multiplier": mult} for ch_id, mult in multipliers]

@app.post("/api/guilds/{guild_id}/multipliers/channels")
async def set_channel_multiplier(guild_id: int, data: ChannelMultiplier):
    """
    Set XP multiplier for a channel
    
    - **guild_id**: Discord Guild ID
    - **channel_id**: Discord Channel ID
    - **multiplier**: Multiplier value (0.1-10.0)
    """
    if data.multiplier < 0 or data.multiplier > 10:
        raise HTTPException(status_code=400, detail="Multiplier must be between 0 and 10")
    
    await db.set_channel_multiplier(guild_id, data.channel_id, data.multiplier)
    return {"success": True, "channel_id": data.channel_id, "multiplier": data.multiplier}

@app.delete("/api/guilds/{guild_id}/multipliers/channels/{channel_id}")
async def remove_channel_multiplier(guild_id: int, channel_id: int):
    """
    Remove XP multiplier from a channel
    
    - **guild_id**: Discord Guild ID
    - **channel_id**: Discord Channel ID
    """
    await db.remove_channel_multiplier(guild_id, channel_id)
    return {"success": True}

@app.get("/api/guilds/{guild_id}/multipliers/roles")
async def get_role_multipliers(guild_id: int):
    """
    Get all role multipliers for a guild
    
    - **guild_id**: Discord Guild ID
    """
    multipliers = await db.get_all_role_multipliers(guild_id)
    return [{"role_id": role_id, "multiplier": mult} for role_id, mult in multipliers]

@app.post("/api/guilds/{guild_id}/multipliers/roles")
async def set_role_multiplier(guild_id: int, data: RoleMultiplier):
    """
    Set XP multiplier for a role
    
    - **guild_id**: Discord Guild ID
    - **role_id**: Discord Role ID
    - **multiplier**: Multiplier value (0.1-10.0)
    """
    if data.multiplier < 0 or data.multiplier > 10:
        raise HTTPException(status_code=400, detail="Multiplier must be between 0 and 10")
    
    await db.set_role_multiplier(guild_id, data.role_id, data.multiplier)
    return {"success": True, "role_id": data.role_id, "multiplier": data.multiplier}

@app.delete("/api/guilds/{guild_id}/multipliers/roles/{role_id}")
async def remove_role_multiplier(guild_id: int, role_id: int):
    """
    Remove XP multiplier from a role
    
    - **guild_id**: Discord Guild ID
    - **role_id**: Discord Role ID
    """
    await db.remove_role_multiplier(guild_id, role_id)
    return {"success": True}

# ==================== LOG CHANNELS ====================

@app.get("/api/guilds/{guild_id}/logs")
async def get_log_channels(guild_id: int):
    """
    Get all log channel settings for a guild
    
    - **guild_id**: Discord Guild ID
    """
    message_log = await db.get_log_channel_id(guild_id)
    voice_log = await db.get_voice_log_channel_id(guild_id)
    level_log = await db.get_level_log_channel_id(guild_id)
    
    return {
        "message_log_channel_id": message_log,
        "voice_log_channel_id": voice_log,
        "level_log_channel_id": level_log
    }

@app.put("/api/guilds/{guild_id}/logs/messages")
async def set_message_log_channel(guild_id: int, data: LogChannel):
    """
    Set message log channel
    
    - **guild_id**: Discord Guild ID
    - **channel_id**: Discord Channel ID
    """
    await db.set_log_channel(guild_id, data.channel_id)
    return {"success": True, "channel_id": data.channel_id}

@app.put("/api/guilds/{guild_id}/logs/voice")
async def set_voice_log_channel(guild_id: int, data: LogChannel):
    """
    Set voice log channel
    
    - **guild_id**: Discord Guild ID
    - **channel_id**: Discord Channel ID
    """
    await db.set_voice_log_channel(guild_id, data.channel_id)
    return {"success": True, "channel_id": data.channel_id}

@app.put("/api/guilds/{guild_id}/logs/levels")
async def set_level_log_channel(guild_id: int, data: LogChannel):
    """
    Set level log channel
    
    - **guild_id**: Discord Guild ID
    - **channel_id**: Discord Channel ID
    """
    await db.set_level_log_channel(guild_id, data.channel_id)
    return {"success": True, "channel_id": data.channel_id}

# ==================== VOICE XP REQUIREMENTS ====================

@app.get("/api/guilds/{guild_id}/voicexp/requirements", response_model=VoiceXPRequirements)
async def get_voice_xp_requirements(guild_id: int):
    """
    Get Voice XP requirements for a guild
    
    - **guild_id**: Discord Guild ID
    """
    requirements = await db.get_voice_xp_requirements(guild_id)
    return requirements

@app.put("/api/guilds/{guild_id}/voicexp/requirements")
async def update_voice_xp_requirements(guild_id: int, data: VoiceXPRequirements):
    """
    Update all Voice XP requirements for a guild
    
    - **guild_id**: Discord Guild ID
    - **require_non_afk**: Whether AFK users get XP
    - **require_non_deaf**: Whether deafened users get XP
    - **require_non_muted**: Whether muted users get XP
    - **require_others_in_channel**: Whether users need others in the channel to get XP
    """
    await db.set_all_voice_xp_requirements(
        guild_id,
        data.require_non_afk,
        data.require_non_deaf,
        data.require_non_muted,
        data.require_others_in_channel
    )
    return {"success": True, "requirements": data}

@app.patch("/api/guilds/{guild_id}/voicexp/requirements")
async def update_single_voice_xp_requirement(guild_id: int, data: VoiceXPRequirementUpdate):
    """
    Update a single Voice XP requirement for a guild
    
    - **guild_id**: Discord Guild ID
    - **requirement**: Name of the requirement to update
    - **value**: New value (True/False)
    """
    valid_requirements = ['require_non_afk', 'require_non_deaf', 'require_non_muted', 'require_others_in_channel']
    
    if data.requirement not in valid_requirements:
        raise HTTPException(status_code=400, detail=f"Invalid requirement. Must be one of: {valid_requirements}")
    
    await db.set_voice_xp_requirement(guild_id, data.requirement, data.value)
    return {"success": True, "requirement": data.requirement, "value": data.value}

# ==================== LEADERBOARD ====================

@app.get("/api/guilds/{guild_id}/leaderboard")
async def get_leaderboard(guild_id: int, limit: int = 50, offset: int = 0):
    """
    Get XP leaderboard for a guild
    
    - **guild_id**: Discord Guild ID
    - **limit**: Number of users to return (default: 50)
    - **offset**: Pagination offset (default: 0)
    """
    leaderboard = await db.get_leaderboard(guild_id, limit + offset)
    
    # Apply offset and limit
    paginated = leaderboard[offset:offset + limit]
    
    # Format with rank
    formatted = [
        {
            "user_id": str(user_id),
            "username": None,  # Will be fetched by frontend
            "discriminator": None,
            "avatar": None,
            "total_xp": xp,
            "level": level,
            "rank": idx + 1 + offset
        }
        for idx, (user_id, xp, level) in enumerate(paginated)
    ]
    
    return {
        "leaderboard": formatted,
        "total": len(leaderboard),
        "limit": limit,
        "offset": offset
    }

# ==================== STATS ====================

@app.get("/api/guilds/{guild_id}/stats")
async def get_guild_stats(guild_id: int):
    """
    Get general statistics for a guild
    
    - **guild_id**: Discord Guild ID
    """
    # Add stats functions as needed
    return {
        "total_users": 0,  # Implement these
        "total_messages": 0,
        "total_xp_granted": 0,
        "active_voice_sessions": 0
    }

# ==================== LEVEL ROLES ====================

@app.get("/api/guilds/{guild_id}/level-roles")
async def get_level_roles(guild_id: int):
    """
    Get all level roles for a guild
    
    - **guild_id**: Discord Guild ID
    """
    level_roles = await db.get_all_level_roles(guild_id)
    return [{"level": level, "role_id": role_id} for level, role_id in level_roles]

@app.post("/api/guilds/{guild_id}/level-roles")
async def add_level_role(guild_id: int, data: LevelRole):
    """
    Add a level role
    
    - **guild_id**: Discord Guild ID
    - **level**: Level required for the role
    - **role_id**: Discord Role ID
    """
    await db.add_level_role(guild_id, data.level, data.role_id)
    return {"success": True, "level": data.level, "role_id": data.role_id}

@app.delete("/api/guilds/{guild_id}/level-roles/{level}")
async def remove_level_role(guild_id: int, level: int):
    """
    Remove a level role
    
    - **guild_id**: Discord Guild ID
    - **level**: Level of the role to remove
    """
    await db.remove_level_role(guild_id, level)
    return {"success": True, "level": level}

# ==================== AUTO ROLES ====================

@app.get("/api/guilds/{guild_id}/auto-roles")
async def get_auto_roles(guild_id: int):
    """
    Get auto role settings for a guild
    
    - **guild_id**: Discord Guild ID
    """
    settings = await db.get_autorole_settings(guild_id)
    return settings

@app.post("/api/guilds/{guild_id}/auto-roles")
async def add_auto_role(guild_id: int, data: AutoRole):
    """
    Add an auto role
    
    - **guild_id**: Discord Guild ID
    - **role_id**: Discord Role ID
    """
    await db.add_autorole(guild_id, data.role_id)
    return {"success": True, "role_id": data.role_id}

@app.delete("/api/guilds/{guild_id}/auto-roles/{role_id}")
async def remove_auto_role(guild_id: int, role_id: int):
    """
    Remove an auto role
    
    - **guild_id**: Discord Guild ID
    - **role_id**: Discord Role ID to remove
    """
    await db.remove_autorole(guild_id, role_id)
    return {"success": True, "role_id": role_id}

@app.put("/api/guilds/{guild_id}/auto-roles/enabled")
async def set_auto_roles_enabled(guild_id: int, enabled: bool):
    """
    Enable or disable auto roles
    
    - **guild_id**: Discord Guild ID
    - **enabled**: Whether auto roles are enabled
    """
    await db.set_autorole_enabled(guild_id, enabled)
    return {"success": True, "enabled": enabled}

# ==================== PARENT ROLES ====================

@app.get("/api/guilds/{guild_id}/parent-roles")
async def get_parent_roles(guild_id: int):
    """
    Get all parent roles for a guild
    
    - **guild_id**: Discord Guild ID
    """
    parent_roles = await db.get_all_parent_roles(guild_id)
    return [
        {"parent_role_id": parent_id, "child_role_ids": child_ids}
        for parent_id, child_ids in parent_roles
    ]

@app.post("/api/guilds/{guild_id}/parent-roles")
async def add_parent_role(guild_id: int, data: ParentRole):
    """
    Add a parent role
    
    - **guild_id**: Discord Guild ID
    - **parent_role_id**: Discord Role ID to be the parent
    - **child_role_ids**: Optional list of child role IDs
    """
    await db.add_parent_role(guild_id, data.parent_role_id, data.child_role_ids)
    return {"success": True, "parent_role_id": data.parent_role_id}

@app.delete("/api/guilds/{guild_id}/parent-roles/{parent_role_id}")
async def remove_parent_role(guild_id: int, parent_role_id: int):
    """
    Remove a parent role
    
    - **guild_id**: Discord Guild ID
    - **parent_role_id**: Parent role ID to remove
    """
    await db.remove_parent_role(guild_id, parent_role_id)
    return {"success": True, "parent_role_id": parent_role_id}

@app.post("/api/guilds/{guild_id}/parent-roles/{parent_role_id}/children")
async def add_child_role(guild_id: int, parent_role_id: int, data: ChildRole):
    """
    Add a child role to a parent role
    
    - **guild_id**: Discord Guild ID
    - **parent_role_id**: Parent role ID
    - **child_role_id**: Child role ID to add
    """
    await db.add_child_to_parent(guild_id, parent_role_id, data.child_role_id)
    return {"success": True, "parent_role_id": parent_role_id, "child_role_id": data.child_role_id}

@app.delete("/api/guilds/{guild_id}/parent-roles/{parent_role_id}/children/{child_role_id}")
async def remove_child_role(guild_id: int, parent_role_id: int, child_role_id: int):
    """
    Remove a child role from a parent role
    
    - **guild_id**: Discord Guild ID
    - **parent_role_id**: Parent role ID
    - **child_role_id**: Child role ID to remove
    """
    await db.remove_child_from_parent(guild_id, parent_role_id, child_role_id)
    return {"success": True, "parent_role_id": parent_role_id, "child_role_id": child_role_id}

# ==================== VERIFICATION ====================

@app.get("/api/guilds/{guild_id}/verification")
async def get_verification(guild_id: int):
    """
    Get verification settings for a guild
    
    - **guild_id**: Discord Guild ID
    """
    verification = await db.get_verification(guild_id)
    if verification:
        message_id, channel_id, role_id = verification
        return {
            "message_id": message_id,
            "channel_id": channel_id,
            "role_id": role_id,
            "enabled": True
        }
    return {"enabled": False}

@app.post("/api/guilds/{guild_id}/verification")
async def set_verification(guild_id: int, data: Verification):
    """
    Set verification settings
    
    - **guild_id**: Discord Guild ID
    - **message_id**: Discord Message ID for verification
    - **channel_id**: Discord Channel ID
    - **role_id**: Discord Role ID to grant on verification
    """
    await db.set_verification(guild_id, data.message_id, data.channel_id, data.role_id)
    return {"success": True, "message_id": data.message_id}

@app.delete("/api/guilds/{guild_id}/verification")
async def remove_verification(guild_id: int):
    """
    Remove verification settings
    
    - **guild_id**: Discord Guild ID
    """
    await db.remove_verification(guild_id)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

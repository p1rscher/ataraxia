# core/database_pg.py - PostgreSQL Version
import asyncpg
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Connection Pool
_pool: Optional[asyncpg.Pool] = None

async def init_db():
    """Initializes the database connection and creates tables"""
    global _pool

    # Get DB URL from .env
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.error("DATABASE_URL not found in .env!")
        return

    # Create Connection Pool
    _pool = await asyncpg.create_pool(db_url, min_size=5, max_size=20)

    # Create Tables
    async with _pool.acquire() as conn:
        # Guild Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                message_log_channel_id BIGINT,
                level_log_channel_id BIGINT,
                voice_log_channel_id BIGINT
            )
        """)
        
        
        # Messages
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                channel_id BIGINT,
                author_id BIGINT,
                content TEXT,
                created_at TIMESTAMP,
                edited_at TIMESTAMP,
                deleted_at TIMESTAMP,
                current_version INTEGER DEFAULT 1
            )
        """)
        
        # Message Versions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS message_versions (
                version_id SERIAL PRIMARY KEY,
                message_id BIGINT,
                content TEXT,
                version_number INTEGER,
                edited_at TIMESTAMP
            )
        """)
        
        # Verification
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS verification (
                guild_id BIGINT PRIMARY KEY,
                message_id BIGINT,
                channel_id BIGINT,
                role_id BIGINT
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS welcome_message (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                message TEXT
            
            )
        """)
        
        # Temp Voice Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_voice_settings (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                join_channel_id BIGINT NOT NULL UNIQUE,
                category_id BIGINT
            )
        """)
        
        # Temp Voice Channels
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_voice_channels (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                owner_id BIGINT
            )
        """)
        
        # Temp Voice Control
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_voice_control (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL
            )
        """)
        
        # Stat Channels
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stat_channels (
                guild_id BIGINT NOT NULL,
                channel_id BIGINT PRIMARY KEY,
                stat_type TEXT NOT NULL
            )
        """)
        
        # Bump Reminder Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bump_settings (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                bump_role_id BIGINT,
                reminder_channel_id BIGINT,
                last_bump_time TIMESTAMP,
                reminder_id BIGINT
            )
        """)
        
        # Autorole Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS autorole_settings (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                role_ids BIGINT[] DEFAULT ARRAY[]::BIGINT[]
            )
        """)
        
        # Parent Roles Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS parent_roles (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                parent_role_id BIGINT NOT NULL,
                child_role_ids BIGINT[] DEFAULT ARRAY[]::BIGINT[],
                UNIQUE(guild_id, parent_role_id)
            )
        """)
        
        # Command Usage Tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS command_usage (
                id SERIAL PRIMARY KEY,
                command_name TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                guild_id BIGINT,
                used_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC')
            )
        """)
        
        # Create indexes for faster queries
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_usage_date 
            ON command_usage(used_at)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_usage_command 
            ON command_usage(command_name)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                multiplier REAL DEFAULT 1.0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # XP Settings per Guild
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS xp_settings (
                guild_id BIGINT PRIMARY KEY,
                message_cooldown INTEGER DEFAULT 60,
                voice_interval INTEGER DEFAULT 60,
                message_xp_min INTEGER DEFAULT 40,
                message_xp_max INTEGER DEFAULT 60,
                voice_xp_min INTEGER DEFAULT 7,
                voice_xp_max INTEGER DEFAULT 10
            )
        """)
        
        # Voice XP Requirements per Guild
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_xp_requirements (
                guild_id BIGINT PRIMARY KEY,
                require_non_afk BOOLEAN DEFAULT TRUE,
                require_non_deaf BOOLEAN DEFAULT TRUE,
                require_non_muted BOOLEAN DEFAULT FALSE,
                require_others_in_channel BOOLEAN DEFAULT TRUE
            )
        """)
        
        # XP Cooldown Tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS xp_cooldowns (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                last_message_xp TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # Voice Sessions for XP tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                joined_at TIMESTAMP NOT NULL,
                last_xp_grant TIMESTAMP NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_sessions_user 
            ON voice_sessions(user_id, guild_id)
        """)

        # XP Channel Multipliers
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS xp_channel_multipliers (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                multiplier REAL NOT NULL,
                UNIQUE(guild_id, channel_id)
            )
        """)

        # XP Role Multipliers
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS xp_role_multipliers (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                multiplier REAL NOT NULL,
                UNIQUE(guild_id, role_id)
            )
        """)

        # Premium Users Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id BIGINT PRIMARY KEY,
                tier TEXT DEFAULT 'free',
                expires_at TIMESTAMP,
                activated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Counting Channels Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS counting_channels (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                current_number INTEGER DEFAULT 0,
                high_score INTEGER DEFAULT 0,
                last_user_id BIGINT
            )
        """)

        # Counting User Stats Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS counting_stats (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                correct_counts INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Level Roles Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS level_roles (
                guild_id BIGINT NOT NULL,
                level INTEGER NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, level)
            )
        """)

    logger.info("Database initialized successfully!")

async def close_db():
    """Closes the database connection"""
    global _pool
    if _pool:
        await _pool.close()

# Helper for ISO timestamp
def get_iso_now():
    # Return as naive datetime in UTC (for asyncpg compatibility)
    return datetime.now(timezone.utc).replace(tzinfo=None)

def ensure_datetime(value):
    """Converts various timestamp formats to a datetime object"""
    
    if value is None:
        return None
    
    # If it is a datetime
    if isinstance(value, datetime):
        # asyncpg/Supabase Pooler has issues with timezone-aware datetime
        # Convert to UTC and remove timezone info (naive datetime in UTC)
        if value.tzinfo is not None:
            # Convert to UTC if not already
            utc_dt = value.astimezone(timezone.utc)
            # Remove tzinfo
            return utc_dt.replace(tzinfo=None)
        return value
    
    # If it is a string, parse it
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            # Remove timezone
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except:
            return None
    
    return None

# ==================== LOG CHANNEL ====================

async def set_log_channel(guild_id: int, channel_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO guild_settings (guild_id, message_log_channel_id) VALUES ($1, $2) "
            "ON CONFLICT (guild_id) DO UPDATE SET message_log_channel_id = $2",
            guild_id, channel_id
        )

async def clear_log_channel(guild_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM guild_settings WHERE guild_id = $1",
            guild_id
        )

async def get_log_channel_id(guild_id: int) -> Optional[int]:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_log_channel_id FROM guild_settings WHERE guild_id = $1",
            guild_id
        )
        return row['message_log_channel_id'] if row else None

async def set_level_log_channel(guild_id: int, channel_id: int):
    """Set the level-up log channel for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO guild_settings (guild_id, level_log_channel_id) VALUES ($1, $2) "
            "ON CONFLICT (guild_id) DO UPDATE SET level_log_channel_id = $2",
            guild_id, channel_id
        )

async def remove_level_log_channel(guild_id: int):
    """Remove the level-up log channel for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE guild_settings SET level_log_channel_id = NULL WHERE guild_id = $1",
            guild_id
        )

async def get_level_log_channel_id(guild_id: int) -> Optional[int]:
    """Get the level-up log channel for a guild"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT level_log_channel_id FROM guild_settings WHERE guild_id = $1",
            guild_id
        )
        return row['level_log_channel_id'] if row else None

async def set_voice_log_channel(guild_id: int, channel_id: int):
    """Set the voice log channel for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO guild_settings (guild_id, voice_log_channel_id) VALUES ($1, $2) "
            "ON CONFLICT (guild_id) DO UPDATE SET voice_log_channel_id = $2",
            guild_id, channel_id
        )

async def remove_voice_log_channel(guild_id: int):
    """Remove the voice log channel for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE guild_settings SET voice_log_channel_id = NULL WHERE guild_id = $1",
            guild_id
        )

async def get_voice_log_channel_id(guild_id: int) -> Optional[int]:
    """Get the voice log channel for a guild"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT voice_log_channel_id FROM guild_settings WHERE guild_id = $1",
            guild_id
        )
        return row['voice_log_channel_id'] if row else None

# ==================== MESSAGES ====================

async def save_message(message_id: int, guild_id: int, channel_id: int,
                       author_id: int, content: str, created_at=None,
                       edited_at=None, force_update: bool = False):
    if created_at is None:
        created_at = get_iso_now()
    else:
        created_at = ensure_datetime(created_at)
    
    if edited_at is not None:
        edited_at = ensure_datetime(edited_at)
    
    async with _pool.acquire() as conn:
        # Check if message exists
        existing = await conn.fetchrow(
            "SELECT content, current_version, created_at, edited_at FROM messages WHERE message_id = $1",
            message_id
        )
        
        if existing:
            old_content = existing['content']
            current_version = existing['current_version']
            msg_created_at = existing['created_at']
            msg_edited_at = existing['edited_at']
            
            if old_content != content or force_update:
                # Determine timestamp for version
                if current_version == 1:
                    version_timestamp = edited_at or msg_edited_at or msg_created_at
                else:
                    version_timestamp = edited_at or msg_edited_at or get_iso_now()
                
                # Save old version
                await conn.execute(
                    "INSERT INTO message_versions (message_id, content, version_number, edited_at) VALUES ($1, $2, $3, $4)",
                    message_id, old_content, current_version, version_timestamp
                )
                
                # Haupteintrag aktualisieren
                new_edited_at = edited_at or get_iso_now()
                await conn.execute(
                    "UPDATE messages SET content = $1, current_version = $2, edited_at = $3 WHERE message_id = $4",
                    content, current_version + 1, new_edited_at, message_id
                )
        else:
            # Neue Nachricht
            await conn.execute(
                "INSERT INTO messages (message_id, guild_id, channel_id, author_id, content, created_at, edited_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                message_id, guild_id, channel_id, author_id, content, created_at, edited_at
            )

async def get_message(message_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT message_id, guild_id, channel_id, author_id, content, created_at, edited_at, deleted_at, current_version FROM messages WHERE message_id = $1",
            message_id
        )

async def mark_message_deleted(message_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET deleted_at = $1 WHERE message_id = $2",
            get_iso_now(), message_id
        )

# ==================== VERIFICATION ====================

async def set_verification(guild_id: int, message_id: int, channel_id: int, role_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO verification (guild_id, message_id, channel_id, role_id) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (guild_id) DO UPDATE SET message_id = $2, channel_id = $3, role_id = $4",
            guild_id, message_id, channel_id, role_id
        )

async def get_verification(guild_id: int):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_id, channel_id, role_id FROM verification WHERE guild_id = $1",
            guild_id
        )
        return (row['message_id'], row['channel_id'], row['role_id']) if row else None

async def remove_verification(guild_id: int):
    """Remove verification settings for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM verification WHERE guild_id = $1",
            guild_id
        )


# ================= WELCOME MESSAGE ==================

async def set_welcome_message(guild_id: int, channel_id: int, message: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO welcome_message (guild_id, channel_id, message) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, message = $3",
            guild_id, channel_id, message
        )

async def get_welcome_message(guild_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT channel_id, message FROM welcome_message WHERE guild_id = $1",
            guild_id
        )


# ==================== TEMP VOICE ====================

async def set_temp_voice_setup(guild_id: int, creator_channel_id: int, category_id: int = None):
    async with _pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT 1 FROM temp_voice_settings WHERE join_channel_id = $1",
            creator_channel_id
        )
        
        if existing:
            await conn.execute(
                "UPDATE temp_voice_settings SET category_id = $1 WHERE join_channel_id = $2",
                category_id, creator_channel_id
            )
        else:
            await conn.execute(
                "INSERT INTO temp_voice_settings (guild_id, join_channel_id, category_id) VALUES ($1, $2, $3)",
                guild_id, creator_channel_id, category_id
            )

async def get_temp_voice_setup(guild_id: int):
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT join_channel_id, category_id FROM temp_voice_settings WHERE guild_id = $1",
            guild_id
        )
        return [(row['join_channel_id'], row['category_id']) for row in rows] if rows else []

async def get_temp_voice_creator_info(channel_id: int):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT guild_id, category_id FROM temp_voice_settings WHERE join_channel_id = $1",
            channel_id
        )
        return (row['guild_id'], row['category_id']) if row else None

async def is_temp_voice_creator(channel_id: int) -> bool:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM temp_voice_settings WHERE join_channel_id = $1",
            channel_id
        )
        return row is not None

async def remove_temp_voice_setup(guild_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM temp_voice_settings WHERE guild_id = $1",
            guild_id
        )

async def add_temp_voice_channel(channel_id: int, guild_id: int, owner_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO temp_voice_channels (channel_id, guild_id, owner_id) VALUES ($1, $2, $3) "
            "ON CONFLICT (channel_id) DO NOTHING",
            channel_id, guild_id, owner_id
        )

async def is_temp_voice_channel(channel_id: int) -> bool:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM temp_voice_channels WHERE channel_id = $1",
            channel_id
        )
        return row is not None

async def remove_temp_voice_channel(channel_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM temp_voice_channels WHERE channel_id = $1",
            channel_id
        )

async def get_temp_voice_owner(channel_id: int) -> Optional[int]:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owner_id FROM temp_voice_channels WHERE channel_id = $1",
            channel_id
        )
        return row['owner_id'] if row else None

async def update_temp_voice_owner(channel_id: int, new_owner_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE temp_voice_channels SET owner_id = $1 WHERE channel_id = $2",
            new_owner_id, channel_id
        )

async def get_all_temp_voice_channels(guild_id: int):
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id, owner_id FROM temp_voice_channels WHERE guild_id = $1",
            guild_id
        )
        return [(row['channel_id'], row['owner_id']) for row in rows] if rows else []

async def set_temp_voice_control_channel(guild_id: int, channel_id: int, message_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO temp_voice_control (guild_id, channel_id, message_id) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, message_id = $3",
            guild_id, channel_id, message_id
        )

async def get_temp_voice_control_channel(guild_id: int):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_id, message_id FROM temp_voice_control WHERE guild_id = $1",
            guild_id
        )
        return (row['channel_id'], row['message_id']) if row else None

# ==================== STAT CHANNELS ====================

async def set_stat_channel(guild_id: int, channel_id: int, stat_type: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO stat_channels (guild_id, channel_id, stat_type) VALUES ($1, $2, $3) "
            "ON CONFLICT (channel_id) DO UPDATE SET stat_type = $3",
            guild_id, channel_id, stat_type
        )

async def get_stat_channels(guild_id: int):
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id, stat_type FROM stat_channels WHERE guild_id = $1",
            guild_id
        )
        return [(row['channel_id'], row['stat_type']) for row in rows] if rows else []

async def remove_stat_channel(channel_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM stat_channels WHERE channel_id = $1",
            channel_id
        )

# ==================== BUMP REMINDER FUNCTIONS ====================

async def set_bump_settings(guild_id: int, enabled: bool, bump_role_id: int = None, reminder_channel_id: int = None):
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO bump_settings (guild_id, enabled, bump_role_id, reminder_channel_id) 
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (guild_id) 
               DO UPDATE SET enabled = $2, bump_role_id = $3, reminder_channel_id = $4""",
            guild_id, enabled, bump_role_id, reminder_channel_id
        )

async def get_bump_settings(guild_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM bump_settings WHERE guild_id = $1",
            guild_id
        )

async def update_last_bump(guild_id: int, bump_time):
    bump_time = ensure_datetime(bump_time)
    async with _pool.acquire() as conn:
        # Reset reminder_id to NULL when a new bump occurs
        await conn.execute(
            "UPDATE bump_settings SET last_bump_time = $1, reminder_id = NULL WHERE guild_id = $2",
            bump_time, guild_id
        )

async def update_reminded_id(guild_id: int, message_id: int):
    """Set the reminder message ID when a reminder is sent"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE bump_settings SET reminder_id = $1 WHERE guild_id = $2",
            message_id, guild_id
        )

async def get_all_bump_guilds():
    """Returns all guilds that have bump reminders enabled"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bump_settings WHERE enabled = TRUE"
        )
        return rows if rows else []

# ==================== AUTOROLE FUNCTIONS ====================

async def get_autorole_settings(guild_id: int):
    """Get autorole settings for a guild"""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM autorole_settings WHERE guild_id = $1",
            guild_id
        )

async def set_autorole_enabled(guild_id: int, enabled: bool):
    """Enable or disable autorole for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO autorole_settings (guild_id, enabled) 
               VALUES ($1, $2)
               ON CONFLICT (guild_id) 
               DO UPDATE SET enabled = $2""",
            guild_id, enabled
        )

async def add_autorole(guild_id: int, role_id: int):
    """Add a role to autorole list"""
    async with _pool.acquire() as conn:
        # Get current settings or create new entry
        settings = await conn.fetchrow(
            "SELECT role_ids FROM autorole_settings WHERE guild_id = $1",
            guild_id
        )
        
        if settings:
            role_ids = list(settings['role_ids']) if settings['role_ids'] else []
            if role_id not in role_ids:
                role_ids.append(role_id)
                await conn.execute(
                    "UPDATE autorole_settings SET role_ids = $1 WHERE guild_id = $2",
                    role_ids, guild_id
                )
        else:
            # Create new entry
            await conn.execute(
                "INSERT INTO autorole_settings (guild_id, enabled, role_ids) VALUES ($1, $2, $3)",
                guild_id, False, [role_id]
            )

async def remove_autorole(guild_id: int, role_id: int):
    """Remove a role from autorole list"""
    async with _pool.acquire() as conn:
        settings = await conn.fetchrow(
            "SELECT role_ids FROM autorole_settings WHERE guild_id = $1",
            guild_id
        )
        
        if settings and settings['role_ids']:
            role_ids = list(settings['role_ids'])
            if role_id in role_ids:
                role_ids.remove(role_id)
                await conn.execute(
                    "UPDATE autorole_settings SET role_ids = $1 WHERE guild_id = $2",
                    role_ids, guild_id
                )

async def clear_autoroles(guild_id: int):
    """Clear all autoroles for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE autorole_settings SET role_ids = ARRAY[]::BIGINT[] WHERE guild_id = $1",
            guild_id
        )

# ==================== PARENT ROLES FUNCTIONS ====================

async def get_all_parent_roles(guild_id: int):
    """Get all parent role configurations for a guild"""
    async with _pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM parent_roles WHERE guild_id = $1",
            guild_id
        )

async def get_parent_role(guild_id: int, parent_role_id: int):
    """Get specific parent role configuration"""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM parent_roles WHERE guild_id = $1 AND parent_role_id = $2",
            guild_id, parent_role_id
        )

async def add_parent_role(guild_id: int, parent_role_id: int, child_role_ids: list = None):
    """Add or update a parent role configuration"""
    if child_role_ids is None:
        child_role_ids = []
    
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO parent_roles (guild_id, parent_role_id, child_role_ids) 
               VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, parent_role_id) 
               DO UPDATE SET child_role_ids = $3""",
            guild_id, parent_role_id, child_role_ids
        )

async def remove_parent_role(guild_id: int, parent_role_id: int):
    """Remove a parent role configuration"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM parent_roles WHERE guild_id = $1 AND parent_role_id = $2",
            guild_id, parent_role_id
        )

async def add_child_to_parent(guild_id: int, parent_role_id: int, child_role_id: int):
    """Add a child role to a parent role"""
    async with _pool.acquire() as conn:
        # Get current config
        config = await conn.fetchrow(
            "SELECT child_role_ids FROM parent_roles WHERE guild_id = $1 AND parent_role_id = $2",
            guild_id, parent_role_id
        )
        
        if config:
            child_ids = list(config['child_role_ids']) if config['child_role_ids'] else []
            if child_role_id not in child_ids:
                child_ids.append(child_role_id)
                await conn.execute(
                    "UPDATE parent_roles SET child_role_ids = $1 WHERE guild_id = $2 AND parent_role_id = $3",
                    child_ids, guild_id, parent_role_id
                )
        else:
            # Create new parent role config
            await conn.execute(
                "INSERT INTO parent_roles (guild_id, parent_role_id, child_role_ids) VALUES ($1, $2, $3)",
                guild_id, parent_role_id, [child_role_id]
            )

async def remove_child_from_parent(guild_id: int, parent_role_id: int, child_role_id: int):
    """Remove a child role from a parent role"""
    async with _pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT child_role_ids FROM parent_roles WHERE guild_id = $1 AND parent_role_id = $2",
            guild_id, parent_role_id
        )
        
        if config and config['child_role_ids']:
            child_ids = list(config['child_role_ids'])
            if child_role_id in child_ids:
                child_ids.remove(child_role_id)
                await conn.execute(
                    "UPDATE parent_roles SET child_role_ids = $1 WHERE guild_id = $2 AND parent_role_id = $3",
                    child_ids, guild_id, parent_role_id
                )

# ==================== COMMAND USAGE TRACKING ====================

async def log_command_usage(command_name: str, user_id: int, guild_id: int = None):
    """Log a command usage"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO command_usage (command_name, user_id, guild_id) VALUES ($1, $2, $3)",
            command_name, user_id, guild_id
        )

async def get_command_stats(days: int = 1):
    """Get command usage statistics for last X days"""
    async with _pool.acquire() as conn:
        return await conn.fetch("""
            SELECT command_name, COUNT(*) as count
            FROM command_usage
            WHERE used_at > NOW() - INTERVAL '%s days'
            GROUP BY command_name
            ORDER BY count DESC
        """ % days)

async def get_total_commands():
    """Get total number of commands ever executed"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) as total FROM command_usage")
        return row['total'] if row else 0

async def get_daily_active_users():
    """Get number of unique users who used commands in last 24 hours"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM command_usage
            WHERE used_at > NOW() - INTERVAL '1 day'
        """)
        return row['count'] if row else 0

# ==================== USER LEVELING ====================

async def can_gain_message_xp(user_id: int, guild_id: int) -> bool:
    """Check if a user can gain XP from messages (cooldown check)"""
    async with _pool.acquire() as conn:
        # Get the cooldown setting for this guild
        cooldown_row = await conn.fetchrow(
            "SELECT message_cooldown FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        cooldown_seconds = cooldown_row['message_cooldown'] if cooldown_row else 60
        
        # Check last XP gain time
        last_xp_row = await conn.fetchrow(
            "SELECT last_message_xp FROM xp_cooldowns WHERE user_id = $1 AND guild_id = $2",
            user_id, guild_id
        )
        
        if not last_xp_row or not last_xp_row['last_message_xp']:
            return True
        
        # Calculate time since last XP
        from datetime import datetime, timezone
        last_xp_time = last_xp_row['last_message_xp']
        if last_xp_time.tzinfo is None:
            last_xp_time = last_xp_time.replace(tzinfo=timezone.utc)
        
        time_since = (datetime.now(timezone.utc) - last_xp_time).total_seconds()
        return time_since >= cooldown_seconds

async def get_message_xp_range(guild_id: int) -> tuple[int, int]:
    """Get the XP range for messages (min, max)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_xp_min, message_xp_max FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        if row:
            return (row['message_xp_min'], row['message_xp_max'])
        return (40, 60)  # Default

async def get_voice_xp_range(guild_id: int) -> tuple[int, int]:
    """Get the XP range for voice activity (min, max)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT voice_xp_min, voice_xp_max FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        if row:
            return (row['voice_xp_min'], row['voice_xp_max'])
        return (15, 25)  # Default

async def update_message_xp_cooldown(user_id: int, guild_id: int):
    """Update the last message XP time for a user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_cooldowns (user_id, guild_id, last_message_xp) 
               VALUES ($1, $2, NOW()) 
               ON CONFLICT (user_id, guild_id) 
               DO UPDATE SET last_message_xp = NOW()""",
            user_id, guild_id
        )

async def add_xp(user_id: int, guild_id: int, amount: int):
    """Add XP to a user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_levels (user_id, guild_id, xp) VALUES ($1, $2, $3) ON CONFLICT (user_id, guild_id) DO UPDATE SET xp = user_levels.xp + $3",
            user_id, guild_id, amount
        )

async def get_level(user_id: int, guild_id: int):
    """Get the level and XP of a user"""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT level, xp FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id, guild_id
        )

async def set_level(user_id: int, guild_id: int, level: int):
    """Set the level of a user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE user_levels SET level = $1 WHERE user_id = $2 AND guild_id = $3",
            level, user_id, guild_id
        )
    
async def get_multiplier(user_id: int, guild_id: int):
    """Get the XP multiplier of a user"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT multiplier FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id, guild_id
        )
        return row['multiplier'] if row else 1.0

async def set_xp_cooldown(guild_id: int, cooldown_seconds: int):
    """Set the XP cooldown for a guild (in seconds)"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_settings (guild_id, message_cooldown) 
               VALUES ($1, $2) 
               ON CONFLICT (guild_id) 
               DO UPDATE SET message_cooldown = $2""",
            guild_id, cooldown_seconds
        )

async def get_xp_cooldown(guild_id: int) -> int:
    """Get the XP cooldown for a guild (in seconds)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_cooldown FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        return row['message_cooldown'] if row else 60

async def set_voice_xp_interval(guild_id: int, interval_seconds: int):
    """Set the voice XP grant interval for a guild (in seconds)"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_settings (guild_id, voice_interval) 
               VALUES ($1, $2) 
               ON CONFLICT (guild_id) 
               DO UPDATE SET voice_interval = $2""",
            guild_id, interval_seconds
        )

async def get_voice_xp_interval(guild_id: int) -> int:
    """Get the voice XP grant interval for a guild (in seconds)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT voice_interval FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        return row['voice_interval'] if row else 60  # Default 1 minute

async def set_message_xp_range(guild_id: int, min_xp: int, max_xp: int):
    """Set the XP range for messages"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_settings (guild_id, message_xp_min, message_xp_max) 
               VALUES ($1, $2, $3) 
               ON CONFLICT (guild_id) 
               DO UPDATE SET message_xp_min = $2, message_xp_max = $3""",
            guild_id, min_xp, max_xp
        )

async def set_voice_xp_range(guild_id: int, min_xp: int, max_xp: int):
    """Set the XP range for voice activity"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_settings (guild_id, voice_xp_min, voice_xp_max) 
               VALUES ($1, $2, $3) 
               ON CONFLICT (guild_id) 
               DO UPDATE SET voice_xp_min = $2, voice_xp_max = $3""",
            guild_id, min_xp, max_xp
        )

async def get_all_xp_settings(guild_id: int):
    """Get all XP settings for a guild"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM xp_settings WHERE guild_id = $1",
            guild_id
        )
        if row:
            return dict(row)
        return {
            'message_cooldown': 60,
            'voice_interval': 60,
            'message_xp_min': 10,
            'message_xp_max': 20,
            'voice_xp_min': 15,
            'voice_xp_max': 25
        }

async def set_multiplier(user_id: int, guild_id: int, multiplier: float):
    """Set the XP multiplier of a user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_levels (user_id, guild_id, multiplier) VALUES ($1, $2, $3) ON CONFLICT (user_id, guild_id) DO UPDATE SET multiplier = $3",
            user_id, guild_id, multiplier
        )

async def get_leaderboard(guild_id: int, limit: int = 10):
    """Get the XP leaderboard for a guild"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, xp, level FROM user_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2",
            guild_id, limit
        )
        return [(row['user_id'], row['xp'], row['level']) for row in rows] if rows else []

# ==================== XP MULTIPLIERS ====================

async def set_channel_multiplier(guild_id: int, channel_id: int, multiplier: float):
    """Set XP multiplier for a specific channel"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_channel_multipliers (guild_id, channel_id, multiplier) 
               VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, channel_id) 
               DO UPDATE SET multiplier = $3""",
            guild_id, channel_id, multiplier
        )

async def remove_channel_multiplier(guild_id: int, channel_id: int):
    """Remove XP multiplier for a channel"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM xp_channel_multipliers WHERE guild_id = $1 AND channel_id = $2",
            guild_id, channel_id
        )

async def get_channel_multiplier(guild_id: int, channel_id: int) -> float:
    """Get XP multiplier for a channel (returns 1.0 if not set)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT multiplier FROM xp_channel_multipliers WHERE guild_id = $1 AND channel_id = $2",
            guild_id, channel_id
        )
        return row['multiplier'] if row else 1.0

async def get_all_channel_multipliers(guild_id: int):
    """Get all channel multipliers for a guild"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id, multiplier FROM xp_channel_multipliers WHERE guild_id = $1",
            guild_id
        )
        return [(row['channel_id'], row['multiplier']) for row in rows] if rows else []

async def set_role_multiplier(guild_id: int, role_id: int, multiplier: float):
    """Set XP multiplier for a specific role"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO xp_role_multipliers (guild_id, role_id, multiplier) 
               VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, role_id) 
               DO UPDATE SET multiplier = $3""",
            guild_id, role_id, multiplier
        )

async def remove_role_multiplier(guild_id: int, role_id: int):
    """Remove XP multiplier for a role"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM xp_role_multipliers WHERE guild_id = $1 AND role_id = $2",
            guild_id, role_id
        )

async def get_role_multiplier(guild_id: int, role_id: int) -> float:
    """Get XP multiplier for a role (returns 1.0 if not set)"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT multiplier FROM xp_role_multipliers WHERE guild_id = $1 AND role_id = $2",
            guild_id, role_id
        )
        return row['multiplier'] if row else 1.0

async def get_all_role_multipliers(guild_id: int):
    """Get all role multipliers for a guild"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role_id, multiplier FROM xp_role_multipliers WHERE guild_id = $1",
            guild_id
        )
        return [(row['role_id'], row['multiplier']) for row in rows] if rows else []

async def calculate_total_multiplier(member, channel_id: int) -> float:
    """Calculate total XP multiplier for a member in a channel"""
    guild_id = member.guild.id
    
    # Start with base multiplier
    total = 1.0
    
    # Get user's personal multiplier
    user_mult = await get_multiplier(member.id, guild_id)
    total *= user_mult
    
    # Get channel multiplier
    channel_mult = await get_channel_multiplier(guild_id, channel_id)
    total *= channel_mult
    
    # Get highest role multiplier (if user has multiple roles with multipliers)
    role_mults = []
    for role in member.roles:
        role_mult = await get_role_multiplier(guild_id, role.id)
        if role_mult != 1.0:
            role_mults.append(role_mult)
    
    # Apply highest role multiplier
    if role_mults:
        for rm in role_mults:
            total *= rm  # Multiplicative stacking for roles
    
    
    return total

# ==================== VOICE XP TRACKING ====================

async def start_voice_session(user_id: int, guild_id: int, channel_id: int):
    """Start tracking a voice session for a user"""
    now = get_iso_now()
    async with _pool.acquire() as conn:
        # Delete any existing session first to avoid conflicts
        await conn.execute("""
            DELETE FROM voice_sessions 
            WHERE user_id = $1 AND guild_id = $2
        """, user_id, guild_id)
        
        # Insert new session
        await conn.execute("""
            INSERT INTO voice_sessions (user_id, guild_id, channel_id, joined_at, last_xp_grant)
            VALUES ($1, $2, $3, $4, $4)
        """, user_id, guild_id, channel_id, now)

async def end_voice_session(user_id: int, guild_id: int):
    """End a voice session and remove from tracking"""
    async with _pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM voice_sessions 
            WHERE user_id = $1 AND guild_id = $2
        """, user_id, guild_id)

async def get_voice_session(user_id: int, guild_id: int):
    """Get current voice session for a user"""
    async with _pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM voice_sessions 
            WHERE user_id = $1 AND guild_id = $2
        """, user_id, guild_id)

async def update_voice_xp_grant(user_id: int, guild_id: int):
    """Update the last XP grant timestamp for a voice session"""
    now = get_iso_now()
    async with _pool.acquire() as conn:
        await conn.execute("""
            UPDATE voice_sessions 
            SET last_xp_grant = $1 
            WHERE user_id = $2 AND guild_id = $3
        """, now, user_id, guild_id)

async def get_all_active_voice_sessions(min_interval_seconds: int = 60):
    """Get all active voice sessions that need XP grant based on interval"""
    async with _pool.acquire() as conn:
        return await conn.fetch("""
            SELECT user_id, guild_id, channel_id, joined_at, last_xp_grant
            FROM voice_sessions
            WHERE last_xp_grant < NOW() - INTERVAL '%s seconds'
        """ % min_interval_seconds)

# ==================== VOICE XP REQUIREMENTS ====================

async def get_voice_xp_requirements(guild_id: int):
    """Get voice XP requirements for a guild"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT require_non_afk, require_non_deaf, require_non_muted, require_others_in_channel
            FROM voice_xp_requirements
            WHERE guild_id = $1
        """, guild_id)
        
        if row:
            return {
                'require_non_afk': row['require_non_afk'],
                'require_non_deaf': row['require_non_deaf'],
                'require_non_muted': row['require_non_muted'],
                'require_others_in_channel': row['require_others_in_channel']
            }
        else:
            # Return defaults
            return {
                'require_non_afk': True,
                'require_non_deaf': True,
                'require_non_muted': False,
                'require_others_in_channel': True  # By default, require others in channel
            }

async def set_voice_xp_requirement(guild_id: int, requirement: str, value: bool):
    """Set a specific voice XP requirement for a guild"""
    valid_requirements = ['require_non_afk', 'require_non_deaf', 'require_non_muted', 'require_others_in_channel']
    if requirement not in valid_requirements:
        raise ValueError(f"Invalid requirement: {requirement}")
    
    async with _pool.acquire() as conn:
        # Insert or update
        await conn.execute(f"""
            INSERT INTO voice_xp_requirements (guild_id, {requirement})
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET {requirement} = $2
        """, guild_id, value)

async def set_all_voice_xp_requirements(guild_id: int, require_non_afk: bool, require_non_deaf: bool, 
                                       require_non_muted: bool, require_others_in_channel: bool):
    """Set all voice XP requirements at once"""
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO voice_xp_requirements 
                (guild_id, require_non_afk, require_non_deaf, require_non_muted, require_others_in_channel)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id) DO UPDATE SET
                require_non_afk = $2,
                require_non_deaf = $3,
                require_non_muted = $4,
                require_others_in_channel = $5

        """, guild_id, require_non_afk, require_non_deaf, require_non_muted, require_others_in_channel)
    
# ==================== PREMIUM USERS ====================

async def get_user_premium_tier(user_id: int) -> str:
    """Returns: 'free', 'premium', or 'premium_plus'"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT tier, expires_at FROM premium_users 
               WHERE user_id = $1 AND expires_at > NOW()""",
            user_id
        )
        return row['tier'] if row else 'free'

async def set_user_premium(user_id: int, tier: str, days: int = 30):
    """Set premium tier for X days"""
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    # Remove timezone info for asyncpg compatibility
    expires = expires.replace(tzinfo=None)
    
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO premium_users (user_id, tier, expires_at)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id) 
               DO UPDATE SET tier = $2, expires_at = $3""",
            user_id, tier, expires
        )

# Track AI usage
async def save_ai_request(user_id: int, tier: str, tokens_used: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO ai_usage (user_id, tier, tokens_used, timestamp)
            VALUES ($1, $2, $3, NOW())""",
            user_id, tier, tokens_used
        )

async def get_ai_stats(user_id: int, since_days: int = 30):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT SUM(tokens_used) as total_tokens
            FROM ai_usage
            WHERE user_id = $1 AND timestamp > NOW() - INTERVAL '%s days'""",
            user_id, since_days
        )
        return row['total_tokens'] if row and row['total_tokens'] else 0

# ==================== COUNTING CHANNEL ====================

async def set_counting_channel(guild_id: int, channel_id: int):
    """Set up a counting channel for a guild"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO counting_channels (guild_id, channel_id, current_number, high_score)
               VALUES ($1, $2, 0, 0)
               ON CONFLICT (guild_id) 
               DO UPDATE SET channel_id = $2, current_number = 0, high_score = 0, last_user_id = NULL""",
            guild_id, channel_id
        )

async def remove_counting_channel(guild_id: int):
    """Remove counting channel setup"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM counting_channels WHERE guild_id = $1",
            guild_id
        )

async def get_counting_settings(guild_id: int):
    """Get counting channel settings for a guild"""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM counting_channels WHERE guild_id = $1",
            guild_id
        )

async def update_counting(guild_id: int, new_number: int, last_user_id: int):
    """Update the current counting number and last user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """UPDATE counting_channels 
               SET current_number = $2, last_user_id = $3 
               WHERE guild_id = $1""",
            guild_id, new_number, last_user_id
        )

async def reset_counting(guild_id: int):
    """Reset counting to 0"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """UPDATE counting_channels 
               SET current_number = 0, last_user_id = NULL 
               WHERE guild_id = $1""",
            guild_id
        )

async def update_counting_highscore(guild_id: int, high_score: int):
    """Update the high score for counting"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """UPDATE counting_channels 
               SET high_score = $2 
               WHERE guild_id = $1 AND high_score < $2""",
            guild_id, high_score
        )

async def increment_user_counting(guild_id: int, user_id: int):
    """Increment correct count for a user"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO counting_stats (guild_id, user_id, correct_counts)
               VALUES ($1, $2, 1)
               ON CONFLICT (guild_id, user_id)
               DO UPDATE SET correct_counts = counting_stats.correct_counts + 1""",
            guild_id, user_id
        )

async def get_counting_leaderboard(guild_id: int, limit: int = 10):
    """Get counting leaderboard for a guild"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, correct_counts 
               FROM counting_stats 
               WHERE guild_id = $1 
               ORDER BY correct_counts DESC 
               LIMIT $2""",
            guild_id, limit
        )
        return [(row['user_id'], row['correct_counts']) for row in rows] if rows else []

# ==================== LEVEL ROLES ====================

async def add_level_role(guild_id: int, level: int, role_id: int):
    """Add or update a level role reward"""
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO level_roles (guild_id, level, role_id)
               VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, level)
               DO UPDATE SET role_id = $3""",
            guild_id, level, role_id
        )

async def remove_level_role(guild_id: int, level: int):
    """Remove a level role reward"""
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM level_roles WHERE guild_id = $1 AND level = $2",
            guild_id, level
        )

async def get_level_role(guild_id: int, level: int) -> Optional[int]:
    """Get the role ID for a specific level"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role_id FROM level_roles WHERE guild_id = $1 AND level = $2",
            guild_id, level
        )
        return row['role_id'] if row else None

async def get_all_level_roles(guild_id: int):
    """Get all level roles for a guild"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT level, role_id FROM level_roles WHERE guild_id = $1 ORDER BY level ASC",
            guild_id
        )
        return [(row['level'], row['role_id']) for row in rows] if rows else []

async def get_level_roles_up_to(guild_id: int, level: int):
    """Get all level roles up to and including a specific level"""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT level, role_id FROM level_roles WHERE guild_id = $1 AND level <= $2 ORDER BY level ASC",
            guild_id, level
        )
        return [(row['level'], row['role_id']) for row in rows] if rows else []
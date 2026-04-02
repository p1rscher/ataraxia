# utils/stats_updater.py
import asyncio
import json
import logging
from datetime import datetime
from core import database_pg as db

logger = logging.getLogger(__name__)

async def update_stats_json(bot):
    """Update stats.json file for website every 5 minutes"""
    logger.info("update_stats_json: Waiting for bot to be ready...")
    while not bot.is_ready():
        await asyncio.sleep(1)
    logger.info("update_stats_json: Bot ready, starting stats updates")
    
    # Path to website stats file (absolute path)
    stats_file = "/var/www/ataraxia-bot.com/stats.json"
    
    while not bot.is_closed():
        try:
            # Calculate stats
            total_servers = len(bot.guilds)
            total_users = sum(g.member_count for g in bot.guilds)
            total_commands = await db.get_total_commands()
            daily_active_users = await db.get_daily_active_users()
            
            # Create stats object
            stats = {
                "total_servers": total_servers,
                "total_users": total_users,
                "total_commands": total_commands,
                "daily_active_users": daily_active_users,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Write to file
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            
            logger.info(f"Updated stats.json: {total_servers} servers, {total_users} users")
            
        except Exception as e:
            logger.error(f"Failed to update stats.json: {e}", exc_info=True)
        
        # Wait 5 minutes
        await asyncio.sleep(300)

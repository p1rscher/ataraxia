# utils/close.py
import asyncio
import signal
import discord
from typing import Optional
from core import database_pg as db


bot: Optional[discord.Client] = None  # Will be set in main.py

active_sessions = [] # list of aiohttp.ClientSession objects to close on shutdown

async def graceful_shutdown(bot):
    print("Shutting down gracefully...")
    
    # 1. Schließe alle aktiven aiohttp Sessions
    for session in active_sessions:
        if not session.closed:
            await session.close()
    
    # 2. Warte auf alle aktiven Tasks (außer der aktuellen)
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        print(f"Waiting for {len(tasks)} tasks to complete...")
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
        except asyncio.TimeoutError:
            print(f"Timeout waiting for {len(tasks)} tasks")
    
    # 3. close bot connection (closes websockets etc.)
    try:
        await bot.close()
    except Exception as e:
        print(f"Error closing bot: {e}")

    # 4. If you are using a persistent DB connection, close it here
    try:
        from core import database as db
        if hasattr(db, 'close'):
            await db.close()
    except Exception as e:
        print(f"Error closing database: {e}")
    
    # 5. wait a moment for aiohttp cleanup
    await asyncio.sleep(0.25)
    
    # Logs
    print("Shutdown complete!")


def setup_signal_handlers():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return

    def schedule_shutdown():
        # create_task so shutdown runs asynchronously
        asyncio.create_task(graceful_shutdown(bot))

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, schedule_shutdown)
        except NotImplementedError:
            # Not implemented on the current platform
            pass

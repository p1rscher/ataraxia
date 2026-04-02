import discord

# Set database reference from main.py
db = None

async def on_interaction(ctx: discord.Interaction):
    """Monitors commands"""

    # Debug: Show all interactions

    # Check if it's a command
    if ctx.type != discord.InteractionType.application_command:
        return

    # Debug: Show command info
    if ctx.command:
        return

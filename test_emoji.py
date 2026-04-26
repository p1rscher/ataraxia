import sys
import os
sys.path.append('bot')
from bot.cogs.server_management import reaction_roles

print("Heart:", repr(reaction_roles.normalize_emoji("❤️")))
print("Grin:", repr(reaction_roles.normalize_emoji("😀")))
print("Alias:", repr(reaction_roles.normalize_emoji(":smile:")))
print("Custom:", repr(reaction_roles.normalize_emoji("<:peepoHappy:123456789>")))


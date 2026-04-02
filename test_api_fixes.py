#!/usr/bin/env python3
"""
Quick test script to verify API fixes
"""
import requests
import json

API_BASE = "http://localhost:8000"
GUILD_ID = "123456789"

print("🧪 Testing API Fixes...\n")

# Test 1: GET XP Settings
print("1️⃣ GET XP Settings")
response = requests.get(f"{API_BASE}/api/guilds/{GUILD_ID}/xp/settings")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Response: {json.dumps(response.json(), indent=2)}")
else:
    print(f"   ❌ Error: {response.text}")
print()

# Test 2: PUT XP Settings (all at once)
print("2️⃣ PUT XP Settings (all at once)")
settings_data = {
    "message_xp_min": 15,
    "message_xp_max": 25,
    "voice_xp_min": 10,
    "voice_xp_max": 20,
    "message_cooldown": 60,
    "voice_interval": 120
}
response = requests.put(
    f"{API_BASE}/api/guilds/{GUILD_ID}/xp/settings",
    json=settings_data
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Success!")
else:
    print(f"   ❌ Error: {response.text}")
print()

# Test 3: GET Leaderboard
print("3️⃣ GET Leaderboard")
response = requests.get(f"{API_BASE}/api/guilds/{GUILD_ID}/leaderboard?limit=5&offset=0")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   ✅ Total: {data.get('total', 0)}, Returned: {len(data.get('leaderboard', []))}")
    if data.get('leaderboard'):
        print(f"   First entry: {json.dumps(data['leaderboard'][0], indent=2)}")
else:
    print(f"   ❌ Error: {response.text}")
print()

# Test 4: Voice XP Requirements
print("4️⃣ GET Voice XP Requirements")
response = requests.get(f"{API_BASE}/api/guilds/{GUILD_ID}/voicexp/requirements")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Response: {json.dumps(response.json(), indent=2)}")
else:
    print(f"   ❌ Error: {response.text}")
print()

# Test 5: PUT Voice XP Requirements
print("5️⃣ PUT Voice XP Requirements")
requirements_data = {
    "require_non_afk": True,
    "require_non_deaf": True,
    "require_non_muted": False,
    "require_others_in_channel": True
}
response = requests.put(
    f"{API_BASE}/api/guilds/{GUILD_ID}/voicexp/requirements",
    json=requirements_data
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Success!")
else:
    print(f"   ❌ Error: {response.text}")
print()

print("✅ All tests completed!")

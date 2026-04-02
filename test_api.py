"""Test script for Ataraxia API endpoints"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Use a placeholder guild ID - replace with your actual guild ID
GUILD_ID = "123456789"  # Replace this with your actual Discord server ID

def test_health():
    """Test health check endpoint"""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_xp_settings():
    """Test XP settings endpoints"""
    print("\n=== Testing XP Settings ===")
    
    # Get XP settings
    response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/xp/settings")
    print(f"GET XP Settings Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Update message cooldown
    print("\n--- Updating Message Cooldown ---")
    response = requests.put(
        f"{BASE_URL}/api/guilds/{GUILD_ID}/xp/cooldown",
        json={"cooldown": 90}
    )
    print(f"PUT Cooldown Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Update message XP range
    print("\n--- Updating Message XP Range ---")
    response = requests.put(
        f"{BASE_URL}/api/guilds/{GUILD_ID}/xp/messagexp",
        json={"min_xp": 12, "max_xp": 22}
    )
    print(f"PUT Message XP Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_voice_xp_requirements():
    """Test Voice XP requirements endpoints"""
    print("\n=== Testing Voice XP Requirements ===")
    
    # Get requirements
    response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/voicexp/requirements")
    print(f"GET Requirements Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Update single requirement
    print("\n--- Updating Single Requirement ---")
    response = requests.patch(
        f"{BASE_URL}/api/guilds/{GUILD_ID}/voicexp/requirements",
        json={"requirement": "require_non_afk", "value": False}
    )
    print(f"PATCH Requirement Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Update all requirements
    print("\n--- Updating All Requirements ---")
    response = requests.put(
        f"{BASE_URL}/api/guilds/{GUILD_ID}/voicexp/requirements",
        json={
            "require_non_afk": True,
            "require_non_deaf": True,
            "require_non_muted": False,
            "require_others_in_channel": True
        }
    )
    print(f"PUT All Requirements Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_multipliers():
    """Test multiplier endpoints"""
    print("\n=== Testing Multipliers ===")
    
    # Get all multipliers
    response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/multipliers")
    print(f"GET Multipliers Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_logs():
    """Test log channel endpoints"""
    print("\n=== Testing Log Channels ===")
    
    # Get log channels
    response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/logs")
    print(f"GET Logs Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_leaderboard():
    """Test leaderboard endpoint"""
    print("\n=== Testing Leaderboard ===")
    
    # Get leaderboard
    response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/leaderboard?limit=5")
    print(f"GET Leaderboard Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    print("=" * 60)
    print("Ataraxia API Test Script")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Guild ID: {GUILD_ID}")
    print("\nNOTE: Replace GUILD_ID with your actual Discord server ID!")
    print("=" * 60)
    
    try:
        test_health()
        test_xp_settings()
        test_voice_xp_requirements()
        test_multipliers()
        test_logs()
        test_leaderboard()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API!")
        print("Make sure the API is running: uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

// API Client for Ataraxia Bot

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

export interface BotStats {
  total_servers: number;
  total_users: number;
  total_commands: number;
  uptime?: string;
}

export interface XPSettings {
  message_cooldown: number;
  voice_interval: number;
  message_xp_min: number;
  message_xp_max: number;
  voice_xp_min: number;
  voice_xp_max: number;
}

export interface LeaderboardEntry {
  user_id: number;
  xp: number;
  level: number;
}

// Mock data for local development
const MOCK_STATS: BotStats = {
  total_servers: 1245,
  total_users: 52834,
  total_commands: 183920,
  uptime: '99.9%',
};

// Fetch bot stats
export async function getBotStats(): Promise<BotStats> {
  // Use mock data if configured
  if (USE_MOCK_DATA) {
    console.log('Using mock data for development');
    return MOCK_STATS;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/stats.json`, {
      cache: 'no-store', // Always fetch fresh data
      next: { revalidate: 60 }, // Revalidate every 60 seconds
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch bot stats');
    }
    
    return response.json();
  } catch (error) {
    console.error('Error fetching stats, using fallback:', error);
    // Return mock data as fallback
    return MOCK_STATS;
  }
}

// Fetch XP settings for a guild
export async function getXPSettings(guildId: string): Promise<XPSettings> {
  const response = await fetch(`${API_BASE_URL}/api/guilds/${guildId}/xp/settings`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch XP settings');
  }
  
  return response.json();
}

// Update XP cooldown
export async function updateXPCooldown(guildId: string, cooldown: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/guilds/${guildId}/xp/cooldown`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ cooldown }),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update cooldown');
  }
}

// Fetch leaderboard
export async function getLeaderboard(guildId: string, limit: number = 10): Promise<LeaderboardEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/guilds/${guildId}/leaderboard?limit=${limit}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch leaderboard');
  }
  
  return response.json();
}

// Format large numbers with commas
export function formatNumber(num: number): string {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

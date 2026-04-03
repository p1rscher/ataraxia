import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_ANALYTICS = {
  overview: {
    total_messages: 45230,
    total_voice_minutes: 12840,
    active_users: 287,
    total_xp_earned: 1842530,
  },
  top_channels: [
    { channel_id: '123456789', channel_name: 'general', message_count: 12450, xp_earned: 245600 },
    { channel_id: '987654321', channel_name: 'gaming', message_count: 8920, xp_earned: 178400 },
    { channel_id: '456789123', channel_name: 'memes', message_count: 7680, xp_earned: 153600 },
    { channel_id: '789123456', channel_name: 'music', message_count: 5230, xp_earned: 104600 },
    { channel_id: '321654987', channel_name: 'off-topic', message_count: 4150, xp_earned: 83000 },
  ],
  activity_by_hour: [
    { hour: 0, messages: 450, voice_minutes: 120 },
    { hour: 1, messages: 280, voice_minutes: 80 },
    { hour: 2, messages: 150, voice_minutes: 40 },
    { hour: 3, messages: 90, voice_minutes: 25 },
    { hour: 4, messages: 75, voice_minutes: 20 },
    { hour: 5, messages: 120, voice_minutes: 35 },
    { hour: 6, messages: 380, voice_minutes: 90 },
    { hour: 7, messages: 680, voice_minutes: 150 },
    { hour: 8, messages: 920, voice_minutes: 210 },
    { hour: 9, messages: 1250, voice_minutes: 280 },
    { hour: 10, messages: 1580, voice_minutes: 350 },
    { hour: 11, messages: 1820, voice_minutes: 420 },
    { hour: 12, messages: 2100, voice_minutes: 480 },
    { hour: 13, messages: 2350, voice_minutes: 520 },
    { hour: 14, messages: 2480, voice_minutes: 560 },
    { hour: 15, messages: 2650, voice_minutes: 590 },
    { hour: 16, messages: 2850, voice_minutes: 640 },
    { hour: 17, messages: 3120, voice_minutes: 720 },
    { hour: 18, messages: 3450, voice_minutes: 810 },
    { hour: 19, messages: 3680, voice_minutes: 880 },
    { hour: 20, messages: 3520, voice_minutes: 850 },
    { hour: 21, messages: 3200, voice_minutes: 780 },
    { hour: 22, messages: 2650, voice_minutes: 650 },
    { hour: 23, messages: 1850, voice_minutes: 480 },
  ],
  level_distribution: [
    { level_range: '1-5', user_count: 85 },
    { level_range: '6-10', user_count: 72 },
    { level_range: '11-20', user_count: 58 },
    { level_range: '21-30', user_count: 35 },
    { level_range: '31-50', user_count: 22 },
    { level_range: '51+', user_count: 15 },
  ],
};

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const days = parseInt(searchParams.get('days') || '7');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_ANALYTICS);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/analytics?days=${days}`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch analytics');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching analytics:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analytics' },
      { status: 500 }
    );
  }
}

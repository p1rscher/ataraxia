import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_LEADERBOARD = [
  {
    user_id: '278901234567890123',
    username: 'CoolUser',
    discriminator: '0001',
    avatar: 'a_1234567890abcdef1234567890abcdef',
    total_xp: 125430,
    level: 42,
    rank: 1,
  },
  {
    user_id: '389012345678901234',
    username: 'ProGamer',
    discriminator: '0002',
    avatar: '1234567890abcdef1234567890abcdef',
    total_xp: 98765,
    level: 38,
    rank: 2,
  },
  {
    user_id: '490123456789012345',
    username: 'ChatMaster',
    discriminator: '0003',
    avatar: null,
    total_xp: 87654,
    level: 35,
    rank: 3,
  },
  {
    user_id: '501234567890123456',
    username: 'VoiceKing',
    discriminator: '0004',
    avatar: 'b_fedcba0987654321fedcba0987654321',
    total_xp: 76543,
    level: 33,
    rank: 4,
  },
  {
    user_id: '612345678901234567',
    username: 'ActiveUser',
    discriminator: '0005',
    avatar: null,
    total_xp: 65432,
    level: 30,
    rank: 5,
  },
  {
    user_id: '723456789012345678',
    username: 'RegularMember',
    discriminator: '0006',
    avatar: 'c_abcdef1234567890abcdef1234567890',
    total_xp: 54321,
    level: 28,
    rank: 6,
  },
  {
    user_id: '834567890123456789',
    username: 'Chatter',
    discriminator: '0007',
    avatar: null,
    total_xp: 43210,
    level: 25,
    rank: 7,
  },
  {
    user_id: '945678901234567890',
    username: 'NewbiePro',
    discriminator: '0008',
    avatar: 'd_1234abcd5678efgh9012ijkl3456mnop',
    total_xp: 32109,
    level: 22,
    rank: 8,
  },
  {
    user_id: '056789012345678901',
    username: 'Lurker',
    discriminator: '0009',
    avatar: null,
    total_xp: 21098,
    level: 18,
    rank: 9,
  },
  {
    user_id: '167890123456789012',
    username: 'CasualGamer',
    discriminator: '0010',
    avatar: 'e_9876543210fedcba9876543210fedcba',
    total_xp: 10987,
    level: 15,
    rank: 10,
  },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const limit = parseInt(searchParams.get('limit') || '50');
    const offset = parseInt(searchParams.get('offset') || '0');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      const paginatedData = MOCK_LEADERBOARD.slice(offset, offset + limit);
      return NextResponse.json({
        leaderboard: paginatedData,
        total: MOCK_LEADERBOARD.length,
        limit,
        offset,
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/leaderboard?limit=${limit}&offset=${offset}`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch leaderboard');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching leaderboard:', error);
    return NextResponse.json(
      { error: 'Failed to fetch leaderboard' },
      { status: 500 }
    );
  }
}

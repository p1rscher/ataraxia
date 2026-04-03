import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/route';

// Mock data for development
const mockUserProfile = {
  user_id: '123456789',
  username: 'TestUser',
  discriminator: '1234',
  avatar: 'https://cdn.discordapp.com/embed/avatars/0.png',
  level: 42,
  xp: 125840,
  xp_to_next_level: 10500,
  total_messages: 3420,
  total_voice_minutes: 1240,
  rank: 5,
  total_members: 287,
  roles: [
    { id: '1', name: 'Level 40', color: 0x7289da },
    { id: '2', name: 'Active Member', color: 0x43b581 },
    { id: '3', name: 'Verified', color: 0xfaa61a },
  ],
  badges: ['early_supporter', 'active_member', 'voice_veteran'],
  joined_at: '2024-01-15T10:30:00Z',
};

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');
  const userId = searchParams.get('userId');

  if (!guildId) {
    return NextResponse.json({ error: 'Missing guildId' }, { status: 400 });
  }

  // Get session for current user
  const session = await getServerSession(authOptions);
  
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Use userId from query or current user
  const targetUserId = userId || session.user.id;

  const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

  if (useMockData) {
    return NextResponse.json({
      ...mockUserProfile,
      user_id: targetUserId,
    });
  }

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/user-profile?guild_id=${guildId}&user_id=${targetUserId}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch user profile');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching user profile:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

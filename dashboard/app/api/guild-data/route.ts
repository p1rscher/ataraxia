import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/route';

const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_CHANNELS = [
  { id: '123456789', name: 'general', type: 0 },
  { id: '987654321', name: 'bot-commands', type: 0 },
  { id: '456789123', name: 'vip-chat', type: 0 },
  { id: '789123456', name: 'announcements', type: 0 },
  { id: '321654987', name: 'Voice Channel', type: 2 },
];

const MOCK_ROLES = [
  { id: '111222333', name: 'VIP', color: 0xe91e63 },
  { id: '444555666', name: 'Booster', color: 0xf47fff },
  { id: '777888999', name: 'Member', color: 0x99aab5 },
  { id: '111999888', name: 'Moderator', color: 0x5865f2 },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const type = searchParams.get('type'); // 'channels' or 'roles'

    if (!guildId || !type) {
      return NextResponse.json(
        { error: 'Guild ID and type are required' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(type === 'channels' ? MOCK_CHANNELS : MOCK_ROLES);
    }

    const session = await getServerSession(authOptions);
    
    if (!session?.accessToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Fetch guild data from Discord API
    const response = await fetch(
      `https://discord.com/api/guilds/${guildId}/${type}`,
      {
        headers: {
          Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch ${type} from Discord`);
    }

    const data = await response.json();
    
    // Filter text channels only (type 0) for channels
    if (type === 'channels') {
      const filteredChannels = data.filter(
        (ch: any) => ch.type === 0 || ch.type === 2
      );
      return NextResponse.json(filteredChannels);
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching guild data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch guild data' },
      { status: 500 }
    );
  }
}

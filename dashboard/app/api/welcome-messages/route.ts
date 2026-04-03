import { NextRequest, NextResponse } from 'next/server';

// Mock data for development
const mockWelcomeConfig = {
  enabled: true,
  channel_id: '1234567890',
  channel_name: 'welcome',
  message: 'Welcome {user} to **{server}**! 🎉\nYou are member #{member_count}',
  embed_enabled: true,
  embed_title: 'Welcome!',
  embed_description: 'Thanks for joining {server}!',
  embed_color: '#7289da',
  embed_image_url: '',
  embed_thumbnail_url: '',
};

const mockGoodbyeConfig = {
  enabled: false,
  channel_id: '1234567890',
  channel_name: 'goodbye',
  message: '{user} just left the server. We now have {member_count} members.',
};

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');
  const type = searchParams.get('type'); // 'welcome' or 'goodbye'

  if (!guildId || !type) {
    return NextResponse.json({ error: 'Missing guildId or type' }, { status: 400 });
  }

  const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

  if (useMockData) {
    return NextResponse.json(type === 'welcome' ? mockWelcomeConfig : mockGoodbyeConfig);
  }

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/messages/${type}?guild_id=${guildId}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch ${type} config`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`Error fetching ${type} config:`, error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, type, config } = body;

    if (!guildId || !type) {
      return NextResponse.json({ error: 'Missing guildId or type' }, { status: 400 });
    }

    const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

    if (useMockData) {
      return NextResponse.json({ success: true });
    }

    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/messages/${type}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guild_id: guildId,
        ...config,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to update ${type} config`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating message config:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

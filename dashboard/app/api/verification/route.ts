import { NextRequest, NextResponse } from 'next/server';

// Mock data for development
const mockVerificationConfig = {
  enabled: true,
  channel_id: '1234567890',
  channel_name: 'verify',
  role_id: '9876543210',
  role_name: 'Verified',
  title: 'Verification',
  message: 'React with ✅ to get verified and access the server.',
  footer: 'Welcome to our community!',
};

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');

  if (!guildId) {
    return NextResponse.json({ error: 'Missing guildId' }, { status: 400 });
  }

  const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

  if (useMockData) {
    return NextResponse.json(mockVerificationConfig);
  }

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/verification?guild_id=${guildId}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch verification config');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching verification config:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, channelId, roleId, title, message, footer, enabled } = body;

    if (!guildId) {
      return NextResponse.json({ error: 'Missing guildId' }, { status: 400 });
    }

    const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

    if (useMockData) {
      return NextResponse.json({ success: true });
    }

    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/verification`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guild_id: guildId,
        channel_id: channelId,
        role_id: roleId,
        title,
        message,
        footer,
        enabled,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to update verification config');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating verification config:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

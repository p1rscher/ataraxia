import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_CHANNEL_MULTIPLIERS = [
  { channel_id: '123456789', channel_name: 'general', multiplier: 1.5 },
  { channel_id: '987654321', channel_name: 'bot-commands', multiplier: 0.5 },
  { channel_id: '456789123', channel_name: 'vip-chat', multiplier: 2.0 },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_CHANNEL_MULTIPLIERS);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/channels`,
      { cache: 'no-store' }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch channel multipliers');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching channel multipliers:', error);
    return NextResponse.json(
      { error: 'Failed to fetch channel multipliers' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, channel_id, multiplier } = body;

    if (!guildId || !channel_id || multiplier === undefined) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    if (multiplier < 0) {
      return NextResponse.json(
        { error: 'Multiplier must be non-negative' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Channel multiplier added successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/channels`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id, multiplier }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to add channel multiplier');
    }

    return NextResponse.json({
      success: true,
      message: 'Channel multiplier added successfully',
    });
  } catch (error) {
    console.error('Error adding channel multiplier:', error);
    return NextResponse.json(
      { error: 'Failed to add channel multiplier' },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const channelId = searchParams.get('channelId');

    if (!guildId || !channelId) {
      return NextResponse.json(
        { error: 'Guild ID and Channel ID are required' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Channel multiplier removed successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/channels/${channelId}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      throw new Error('Failed to remove channel multiplier');
    }

    return NextResponse.json({
      success: true,
      message: 'Channel multiplier removed successfully',
    });
  } catch (error) {
    console.error('Error removing channel multiplier:', error);
    return NextResponse.json(
      { error: 'Failed to remove channel multiplier' },
      { status: 500 }
    );
  }
}

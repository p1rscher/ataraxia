import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_XP_SETTINGS = {
  message_xp_min: 15,
  message_xp_max: 25,
  voice_xp_min: 10,
  voice_xp_max: 20,
  message_cooldown: 60,
  voice_interval: 60,
};

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_XP_SETTINGS);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/xp/settings`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch XP settings');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching XP settings:', error);
    return NextResponse.json(
      { error: 'Failed to fetch XP settings' },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, ...settings } = body;

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    // Validate settings
    const requiredFields = [
      'message_xp_min',
      'message_xp_max',
      'voice_xp_min',
      'voice_xp_max',
      'message_cooldown',
      'voice_interval',
    ];

    for (const field of requiredFields) {
      if (settings[field] === undefined || settings[field] === null) {
        return NextResponse.json(
          { error: `Missing required field: ${field}` },
          { status: 400 }
        );
      }
    }

    // Validate ranges
    if (settings.message_xp_min > settings.message_xp_max) {
      return NextResponse.json(
        { error: 'message_xp_min must be less than or equal to message_xp_max' },
        { status: 400 }
      );
    }

    if (settings.voice_xp_min > settings.voice_xp_max) {
      return NextResponse.json(
        { error: 'voice_xp_min must be less than or equal to voice_xp_max' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'XP settings updated successfully (mock mode)',
        data: settings,
      });
    }

    // Update all settings in one call
    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/xp/settings`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to update XP settings');
    }

    const data = await response.json();
    return NextResponse.json({
      success: true,
      message: 'XP settings updated successfully',
      data: data.settings || settings,
    });
  } catch (error) {
    console.error('Error updating XP settings:', error);
    return NextResponse.json(
      { error: 'Failed to update XP settings' },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_REQUIREMENTS = {
  require_non_afk: true,
  require_non_deaf: true,
  require_non_muted: false,
  require_non_alone: true,
};

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_REQUIREMENTS);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/voicexp/requirements`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch Voice XP requirements');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching Voice XP requirements:', error);
    return NextResponse.json(
      { error: 'Failed to fetch Voice XP requirements' },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, ...requirements } = body;

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    // Validate requirements
    const requiredFields = [
      'require_non_afk',
      'require_non_deaf',
      'require_non_muted',
      'require_non_alone',
    ];

    for (const field of requiredFields) {
      if (requirements[field] === undefined || requirements[field] === null) {
        return NextResponse.json(
          { error: `Missing required field: ${field}` },
          { status: 400 }
        );
      }
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Voice XP requirements updated successfully (mock mode)',
        requirements,
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/voicexp/requirements`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requirements),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to update Voice XP requirements');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating Voice XP requirements:', error);
    return NextResponse.json(
      { error: 'Failed to update Voice XP requirements' },
      { status: 500 }
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, requirement, value } = body;

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (!requirement) {
      return NextResponse.json({ error: 'Requirement name is required' }, { status: 400 });
    }

    if (value === undefined || value === null) {
      return NextResponse.json({ error: 'Value is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Voice XP requirement updated successfully (mock mode)',
        requirement,
        value,
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/voicexp/requirements`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requirement, value }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to update Voice XP requirement');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating Voice XP requirement:', error);
    return NextResponse.json(
      { error: 'Failed to update Voice XP requirement' },
      { status: 500 }
    );
  }
}

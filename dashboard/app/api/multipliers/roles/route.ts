import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_ROLE_MULTIPLIERS = [
  { role_id: '111222333', role_name: 'VIP', multiplier: 2.0 },
  { role_id: '444555666', role_name: 'Booster', multiplier: 1.5 },
  { role_id: '777888999', role_name: 'Member', multiplier: 1.0 },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_ROLE_MULTIPLIERS);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/roles`,
      { cache: 'no-store' }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch role multipliers');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching role multipliers:', error);
    return NextResponse.json(
      { error: 'Failed to fetch role multipliers' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, role_id, multiplier } = body;

    if (!guildId || !role_id || multiplier === undefined) {
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
        message: 'Role multiplier added successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/roles`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id, multiplier }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to add role multiplier');
    }

    return NextResponse.json({
      success: true,
      message: 'Role multiplier added successfully',
    });
  } catch (error) {
    console.error('Error adding role multiplier:', error);
    return NextResponse.json(
      { error: 'Failed to add role multiplier' },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const roleId = searchParams.get('roleId');

    if (!guildId || !roleId) {
      return NextResponse.json(
        { error: 'Guild ID and Role ID are required' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Role multiplier removed successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/multipliers/roles/${roleId}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      throw new Error('Failed to remove role multiplier');
    }

    return NextResponse.json({
      success: true,
      message: 'Role multiplier removed successfully',
    });
  } catch (error) {
    console.error('Error removing role multiplier:', error);
    return NextResponse.json(
      { error: 'Failed to remove role multiplier' },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_LEVEL_ROLES = [
  { level: 5, role_id: '111222333444555666', role_name: 'Novice' },
  { level: 10, role_id: '222333444555666777', role_name: 'Member' },
  { level: 25, role_id: '333444555666777888', role_name: 'Active' },
  { level: 50, role_id: '444555666777888999', role_name: 'Elite' },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_LEVEL_ROLES);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/level-roles`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch level roles');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching level roles:', error);
    return NextResponse.json(
      { error: 'Failed to fetch level roles' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, level, roleId, roleName } = body;

    if (!guildId || !level || !roleId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    if (level < 1) {
      return NextResponse.json(
        { error: 'Level must be at least 1' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Level role added successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/level-roles`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level, role_id: roleId }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to add level role');
    }

    return NextResponse.json({
      success: true,
      message: 'Level role added successfully',
    });
  } catch (error) {
    console.error('Error adding level role:', error);
    return NextResponse.json(
      { error: 'Failed to add level role' },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');
    const level = searchParams.get('level');

    if (!guildId || !level) {
      return NextResponse.json(
        { error: 'Guild ID and level are required' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Level role removed successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/level-roles/${level}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      throw new Error('Failed to remove level role');
    }

    return NextResponse.json({
      success: true,
      message: 'Level role removed successfully',
    });
  } catch (error) {
    console.error('Error removing level role:', error);
    return NextResponse.json(
      { error: 'Failed to remove level role' },
      { status: 500 }
    );
  }
}

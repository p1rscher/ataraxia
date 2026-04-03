import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

const MOCK_AUTO_ROLES = [
  { role_id: '111222333444555666', role_name: 'Member' },
  { role_id: '222333444555666777', role_name: 'Welcome' },
];

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const guildId = searchParams.get('guildId');

    if (!guildId) {
      return NextResponse.json({ error: 'Guild ID is required' }, { status: 400 });
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json(MOCK_AUTO_ROLES);
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/auto-roles`,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch auto roles');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching auto roles:', error);
    return NextResponse.json(
      { error: 'Failed to fetch auto roles' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, roleId, roleName } = body;

    if (!guildId || !roleId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    if (USE_MOCK_DATA) {
      return NextResponse.json({
        success: true,
        message: 'Auto role added successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/auto-roles`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: roleId }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to add auto role');
    }

    return NextResponse.json({
      success: true,
      message: 'Auto role added successfully',
    });
  } catch (error) {
    console.error('Error adding auto role:', error);
    return NextResponse.json(
      { error: 'Failed to add auto role' },
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
        message: 'Auto role removed successfully (mock mode)',
      });
    }

    const response = await fetch(
      `${API_BASE_URL}/api/guilds/${guildId}/auto-roles/${roleId}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      throw new Error('Failed to remove auto role');
    }

    return NextResponse.json({
      success: true,
      message: 'Auto role removed successfully',
    });
  } catch (error) {
    console.error('Error removing auto role:', error);
    return NextResponse.json(
      { error: 'Failed to remove auto role' },
      { status: 500 }
    );
  }
}

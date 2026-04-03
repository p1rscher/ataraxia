import { NextRequest, NextResponse } from 'next/server';

// Mock data for development
const mockParentRoles = [
  {
    id: '1',
    parent_role_id: '1234567890',
    parent_role_name: 'Age',
    child_role_ids: ['1111111111', '2222222222', '3333333333'],
    child_role_names: ['18+', '21+', '25+'],
  },
  {
    id: '2',
    parent_role_id: '9876543210',
    parent_role_name: 'Pronouns',
    child_role_ids: ['4444444444', '5555555555'],
    child_role_names: ['he/him', 'she/her'],
  },
];

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');

  if (!guildId) {
    return NextResponse.json({ error: 'Missing guildId' }, { status: 400 });
  }

  // Check if we should use mock data
  const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

  if (useMockData) {
    return NextResponse.json(mockParentRoles);
  }

  try {
    // Real API call would go here
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/parent-roles?guild_id=${guildId}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch parent roles');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching parent roles:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { guildId, parentRoleId, childRoleId } = body;

    if (!guildId || !parentRoleId || !childRoleId) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }

    const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

    if (useMockData) {
      // Mock success response
      return NextResponse.json({ success: true });
    }

    // Real API call
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/parent-roles/add-child`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ guild_id: guildId, parent_role_id: parentRoleId, child_role_id: childRoleId }),
    });

    if (!response.ok) {
      throw new Error('Failed to add child role');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error adding child role:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');
  const parentRoleId = searchParams.get('parentRoleId');
  const childRoleId = searchParams.get('childRoleId');

  if (!guildId || !parentRoleId) {
    return NextResponse.json({ error: 'Missing required parameters' }, { status: 400 });
  }

  const useMockData = process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true';

  if (useMockData) {
    return NextResponse.json({ success: true });
  }

  try {
    let url = `${process.env.NEXT_PUBLIC_API_URL}/parent-roles?guild_id=${guildId}&parent_role_id=${parentRoleId}`;
    
    if (childRoleId) {
      // Remove specific child role
      url += `&child_role_id=${childRoleId}`;
    }

    const response = await fetch(url, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete');
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

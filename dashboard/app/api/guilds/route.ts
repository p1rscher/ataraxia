import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/route';

interface DiscordGuild {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  permissions: string;
  features: string[];
}

export async function GET() {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session?.accessToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Fetch user's guilds from Discord API
    const response = await fetch('https://discord.com/api/users/@me/guilds', {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch guilds from Discord');
    }

    const guilds: DiscordGuild[] = await response.json();

    // Filter guilds where user has administrator permissions
    // Administrator permission = 0x8 (8 in decimal)
    const ADMINISTRATOR = 0x8;
    
    const adminGuilds = guilds.filter(guild => {
      // Owner always has admin rights
      if (guild.owner) return true;
      
      // Check if user has administrator permission
      const permissions = BigInt(guild.permissions);
      return (permissions & BigInt(ADMINISTRATOR)) === BigInt(ADMINISTRATOR);
    });
    
    return NextResponse.json(adminGuilds);
  } catch (error) {
    console.error('Error fetching guilds:', error);
    return NextResponse.json(
      { error: 'Failed to fetch guilds' },
      { status: 500 }
    );
  }
}

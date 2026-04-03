'use client';

import { useState, useEffect } from 'react';
import { useServer } from '../../contexts/ServerContext';
import { useSession } from 'next-auth/react';

interface UserProfile {
  user_id: string;
  username: string;
  discriminator: string;
  avatar: string;
  level: number;
  xp: number;
  xp_to_next_level: number;
  total_messages: number;
  total_voice_minutes: number;
  rank: number;
  total_members: number;
  roles: Array<{
    id: string;
    name: string;
    color: number;
  }>;
  badges: string[];
  joined_at: string;
}

export default function ProfilePage() {
  const { selectedServer } = useServer();
  const { data: session } = useSession();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (selectedServer && session?.user?.id) {
      fetchProfile();
    }
  }, [selectedServer, session]);

  const fetchProfile = async () => {
    if (!selectedServer || !session?.user?.id) return;

    try {
      setIsLoading(true);
      const response = await fetch(
        `/api/user-profile?guildId=${selectedServer.id}&userId=${session.user.id}`
      );

      if (response.ok) {
        const data = await response.json();
        setProfile(data);
      }
    } catch (error) {
      console.error('Error fetching profile:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getProgressPercentage = () => {
    if (!profile) return 0;
    const currentLevelXP = profile.xp % profile.xp_to_next_level;
    return (currentLevelXP / profile.xp_to_next_level) * 100;
  };

  const getBadgeEmoji = (badge: string) => {
    const badges: { [key: string]: string } = {
      early_supporter: '🌟',
      active_member: '⚡',
      voice_veteran: '🎤',
      message_master: '💬',
      level_milestone: '🏆',
    };
    return badges[badge] || '🎖️';
  };

  const formatJoinDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  if (!selectedServer) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Please select a server to view your profile</p>
      </div>
    );
  }

  if (isLoading || !profile) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">Your Profile</h1>
        <p className="text-gray-400">Your stats and progress in {selectedServer.name}</p>
      </div>

      {/* Profile Header */}
      <div className="bg-gradient-to-br from-purple-900/40 to-pink-900/40 rounded-lg p-8 border border-purple-700/50 mb-6">
        <div className="flex items-center gap-6">
          <img
            src={profile.avatar || `https://cdn.discordapp.com/embed/avatars/${parseInt(profile.discriminator) % 5}.png`}
            alt={profile.username}
            className="w-24 h-24 rounded-full border-4 border-purple-500"
          />
          <div className="flex-1">
            <h2 className="text-3xl font-bold text-white">
              {profile.username}
              <span className="text-gray-400">#{profile.discriminator}</span>
            </h2>
            <div className="flex items-center gap-4 mt-2">
              <div className="bg-purple-600 px-4 py-1 rounded-full">
                <span className="text-white font-bold">Level {profile.level}</span>
              </div>
              <span className="text-gray-300">
                Rank #{profile.rank} / {profile.total_members}
              </span>
            </div>
          </div>
        </div>

        {/* XP Progress Bar */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-300">Progress to Level {profile.level + 1}</span>
            <span className="text-sm text-gray-300">
              {profile.xp.toLocaleString()} / {(Math.floor(profile.xp / profile.xp_to_next_level) * profile.xp_to_next_level + profile.xp_to_next_level).toLocaleString()} XP
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-4">
            <div
              className="bg-gradient-to-r from-purple-500 to-pink-500 h-4 rounded-full transition-all duration-300"
              style={{ width: `${getProgressPercentage()}%` }}
            ></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Stats */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-xl font-semibold text-white mb-4">📊 Statistics</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Total Messages</span>
              <span className="text-white font-semibold">{profile.total_messages.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Voice Time</span>
              <span className="text-white font-semibold">
                {Math.floor(profile.total_voice_minutes / 60)}h {profile.total_voice_minutes % 60}m
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Total XP</span>
              <span className="text-white font-semibold">{profile.xp.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Member Since</span>
              <span className="text-white font-semibold text-sm">
                {formatJoinDate(profile.joined_at)}
              </span>
            </div>
          </div>
        </div>

        {/* Badges */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-xl font-semibold text-white mb-4">🏅 Badges</h3>
          {profile.badges.length > 0 ? (
            <div className="flex flex-wrap gap-3">
              {profile.badges.map((badge) => (
                <div
                  key={badge}
                  className="bg-gray-700 px-4 py-2 rounded-lg flex items-center gap-2"
                >
                  <span className="text-2xl">{getBadgeEmoji(badge)}</span>
                  <span className="text-white font-medium capitalize">
                    {badge.replace(/_/g, ' ')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400">No badges earned yet</p>
          )}
        </div>
      </div>

      {/* Roles */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-semibold text-white mb-4">👤 Your Roles</h3>
        {profile.roles.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {profile.roles.map((role) => (
              <div
                key={role.id}
                className="px-4 py-2 rounded-full text-sm font-medium"
                style={{
                  backgroundColor: `#${role.color.toString(16).padStart(6, '0')}20`,
                  borderColor: `#${role.color.toString(16).padStart(6, '0')}`,
                  borderWidth: '1px',
                  color: `#${role.color.toString(16).padStart(6, '0')}`,
                }}
              >
                @{role.name}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400">No roles assigned</p>
        )}
      </div>
    </div>
  );
}

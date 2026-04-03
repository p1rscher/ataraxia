'use client';

import { useState, useEffect } from 'react';
import { useServer } from '../../contexts/ServerContext';

interface Analytics {
  overview: {
    total_messages: number;
    total_voice_minutes: number;
    active_users: number;
    total_xp_earned: number;
  };
  top_channels: Array<{
    channel_id: string;
    channel_name: string;
    message_count: number;
    xp_earned: number;
  }>;
  activity_by_hour: Array<{
    hour: number;
    messages: number;
    voice_minutes: number;
  }>;
  level_distribution: Array<{
    level_range: string;
    user_count: number;
  }>;
}

export default function AnalyticsPage() {
  const { selectedServer } = useServer();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(7);

  useEffect(() => {
    if (selectedServer) {
      fetchAnalytics();
    }
  }, [selectedServer, timeRange]);

  const fetchAnalytics = async () => {
    if (!selectedServer) return;

    try {
      setIsLoading(true);
      const response = await fetch(
        `/api/analytics?guildId=${selectedServer.id}&days=${timeRange}`
      );

      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  const getMaxActivity = () => {
    if (!analytics) return 1;
    const max = Math.max(...analytics.activity_by_hour.map((h) => h.messages));
    return max || 1;
  };

  if (!selectedServer) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Please select a server to view analytics</p>
      </div>
    );
  }

  if (isLoading || !analytics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Analytics</h1>
          <p className="text-gray-400">Server activity and statistics</p>
        </div>

        {/* Time Range Selector */}
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(parseInt(e.target.value))}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-gradient-to-br from-purple-900/40 to-purple-800/40 rounded-lg p-6 border border-purple-700/50">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">💬</span>
            <h3 className="text-sm font-medium text-gray-300">Total Messages</h3>
          </div>
          <p className="text-3xl font-bold text-white">{formatNumber(analytics.overview.total_messages)}</p>
        </div>

        <div className="bg-gradient-to-br from-pink-900/40 to-pink-800/40 rounded-lg p-6 border border-pink-700/50">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">🎤</span>
            <h3 className="text-sm font-medium text-gray-300">Voice Minutes</h3>
          </div>
          <p className="text-3xl font-bold text-white">{formatNumber(analytics.overview.total_voice_minutes)}</p>
        </div>

        <div className="bg-gradient-to-br from-blue-900/40 to-blue-800/40 rounded-lg p-6 border border-blue-700/50">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">👥</span>
            <h3 className="text-sm font-medium text-gray-300">Active Users</h3>
          </div>
          <p className="text-3xl font-bold text-white">{formatNumber(analytics.overview.active_users)}</p>
        </div>

        <div className="bg-gradient-to-br from-green-900/40 to-green-800/40 rounded-lg p-6 border border-green-700/50">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">⚡</span>
            <h3 className="text-sm font-medium text-gray-300">Total XP Earned</h3>
          </div>
          <p className="text-3xl font-bold text-white">{formatNumber(analytics.overview.total_xp_earned)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Top Channels */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">📊</span>
            Top Channels
          </h2>
          <div className="space-y-3">
            {analytics.top_channels.map((channel, index) => (
              <div key={channel.channel_id} className="flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1">
                  <span className="text-gray-400 font-semibold w-6">#{index + 1}</span>
                  <div className="flex-1">
                    <p className="text-white font-medium">#{channel.channel_name}</p>
                    <div className="w-full bg-gray-700 rounded-full h-2 mt-1">
                      <div
                        className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full"
                        style={{
                          width: `${(channel.message_count / analytics.top_channels[0].message_count) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
                <div className="text-right ml-4">
                  <p className="text-white font-semibold">{formatNumber(channel.message_count)}</p>
                  <p className="text-xs text-gray-400">{formatNumber(channel.xp_earned)} XP</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Level Distribution */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">📈</span>
            Level Distribution
          </h2>
          <div className="space-y-3">
            {analytics.level_distribution.map((range) => {
              const maxUsers = Math.max(...analytics.level_distribution.map((r) => r.user_count));
              return (
                <div key={range.level_range} className="flex items-center gap-3">
                  <span className="text-gray-300 font-semibold w-16 text-sm">Lvl {range.level_range}</span>
                  <div className="flex-1">
                    <div className="w-full bg-gray-700 rounded-full h-6">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-purple-500 h-6 rounded-full flex items-center justify-end pr-2"
                        style={{
                          width: `${(range.user_count / maxUsers) * 100}%`,
                        }}
                      >
                        <span className="text-white text-xs font-semibold">{range.user_count}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Activity by Hour */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="text-2xl">🕐</span>
          Activity by Hour
        </h2>
        <div className="relative h-64 flex items-end justify-between gap-1">
          {analytics.activity_by_hour.map((hour) => {
            const heightPercent = (hour.messages / getMaxActivity()) * 100;
            return (
              <div key={hour.hour} className="flex-1 flex flex-col items-center gap-2 h-full">
                <div className="w-full flex items-end h-full">
                  <div
                    className="w-full bg-gradient-to-t from-purple-600 to-pink-500 rounded-t hover:from-purple-500 hover:to-pink-400 transition-all cursor-pointer relative group"
                    style={{ height: `${heightPercent}%`, minHeight: heightPercent > 0 ? '4px' : '0' }}
                  >
                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                      {hour.messages} msgs
                      <br />
                      {hour.voice_minutes} mins
                    </div>
                  </div>
                </div>
                <span className="text-xs text-gray-400 mt-auto">{hour.hour}</span>
              </div>
            );
          })}
        </div>
        <div className="mt-4 text-center text-sm text-gray-400">
          Hover over bars to see details
        </div>
      </div>
    </div>
  );
}

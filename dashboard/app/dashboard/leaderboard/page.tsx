'use client';

import { useState, useEffect } from 'react';
import { useServer } from '../../contexts/ServerContext';

interface LeaderboardEntry {
  user_id: string;
  username: string;
  discriminator: string;
  avatar: string | null;
  total_xp: number;
  level: number;
  rank: number;
}

export default function LeaderboardPage() {
  const { selectedServer } = useServer();
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const itemsPerPage = 50;

  useEffect(() => {
    if (selectedServer) {
      fetchLeaderboard();
    }
  }, [selectedServer, currentPage]);

  const fetchLeaderboard = async () => {
    if (!selectedServer) return;

    try {
      setIsLoading(true);
      const offset = (currentPage - 1) * itemsPerPage;
      const response = await fetch(
        `/api/leaderboard?guildId=${selectedServer.id}&limit=${itemsPerPage}&offset=${offset}`
      );

      if (response.ok) {
        const data = await response.json();
        setLeaderboard(data.leaderboard || data);
        setTotalUsers(data.total || data.length);
      }
    } catch (error) {
      console.error('Error fetching leaderboard:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getAvatarUrl = (entry: LeaderboardEntry) => {
    if (!entry.avatar) return null;
    const format = entry.avatar.startsWith('a_') ? 'gif' : 'png';
    return `https://cdn.discordapp.com/avatars/${entry.user_id}/${entry.avatar}.${format}?size=128`;
  };

  const formatXP = (xp: number) => {
    return xp.toLocaleString();
  };

  const getMedalEmoji = (rank: number) => {
    switch (rank) {
      case 1: return '🥇';
      case 2: return '🥈';
      case 3: return '🥉';
      default: return null;
    }
  };

  const totalPages = Math.ceil(totalUsers / itemsPerPage);

  if (!selectedServer) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Please select a server to view the leaderboard</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">Leaderboard</h1>
        <p className="text-gray-400">Top members ranked by XP and level</p>
      </div>

      {/* Top 3 Podium */}
      {leaderboard.length >= 3 && currentPage === 1 && (
        <div className="mb-8 grid grid-cols-3 gap-4 max-w-3xl mx-auto">
          {/* 2nd Place */}
          <div className="flex flex-col items-center pt-12">
            <div className="relative mb-3">
              <div className="absolute -top-2 -right-2 text-3xl">🥈</div>
              {getAvatarUrl(leaderboard[1]) ? (
                <img
                  src={getAvatarUrl(leaderboard[1])!}
                  alt={leaderboard[1].username}
                  className="w-20 h-20 rounded-full border-4 border-gray-400"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-gray-600 border-4 border-gray-400 flex items-center justify-center text-2xl font-bold text-white">
                  {leaderboard[1].username.charAt(0).toUpperCase()}
                </div>
              )}
            </div>
            <div className="text-center">
              <p className="font-bold text-white truncate max-w-[120px]">{leaderboard[1].username}</p>
              <p className="text-sm text-purple-400">Level {leaderboard[1].level}</p>
              <p className="text-xs text-gray-400">{formatXP(leaderboard[1].total_xp)} XP</p>
            </div>
          </div>

          {/* 1st Place */}
          <div className="flex flex-col items-center">
            <div className="relative mb-3">
              <div className="absolute -top-2 -right-2 text-4xl">🥇</div>
              {getAvatarUrl(leaderboard[0]) ? (
                <img
                  src={getAvatarUrl(leaderboard[0])!}
                  alt={leaderboard[0].username}
                  className="w-24 h-24 rounded-full border-4 border-yellow-400 shadow-lg shadow-yellow-400/50"
                />
              ) : (
                <div className="w-24 h-24 rounded-full bg-yellow-600 border-4 border-yellow-400 shadow-lg shadow-yellow-400/50 flex items-center justify-center text-3xl font-bold text-white">
                  {leaderboard[0].username.charAt(0).toUpperCase()}
                </div>
              )}
            </div>
            <div className="text-center">
              <p className="font-bold text-white text-lg truncate max-w-[140px]">{leaderboard[0].username}</p>
              <p className="text-sm text-purple-400">Level {leaderboard[0].level}</p>
              <p className="text-xs text-gray-400">{formatXP(leaderboard[0].total_xp)} XP</p>
            </div>
          </div>

          {/* 3rd Place */}
          <div className="flex flex-col items-center pt-16">
            <div className="relative mb-3">
              <div className="absolute -top-2 -right-2 text-3xl">🥉</div>
              {getAvatarUrl(leaderboard[2]) ? (
                <img
                  src={getAvatarUrl(leaderboard[2])!}
                  alt={leaderboard[2].username}
                  className="w-20 h-20 rounded-full border-4 border-orange-400"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-orange-600 border-4 border-orange-400 flex items-center justify-center text-2xl font-bold text-white">
                  {leaderboard[2].username.charAt(0).toUpperCase()}
                </div>
              )}
            </div>
            <div className="text-center">
              <p className="font-bold text-white truncate max-w-[120px]">{leaderboard[2].username}</p>
              <p className="text-sm text-purple-400">Level {leaderboard[2].level}</p>
              <p className="text-xs text-gray-400">{formatXP(leaderboard[2].total_xp)} XP</p>
            </div>
          </div>
        </div>
      )}

      {/* Leaderboard Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300 w-20">
                Rank
              </th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                User
              </th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                Level
              </th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                Total XP
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {leaderboard.map((entry) => (
              <tr key={entry.user_id} className="hover:bg-gray-700/50 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    {getMedalEmoji(entry.rank) && (
                      <span className="text-2xl">{getMedalEmoji(entry.rank)}</span>
                    )}
                    <span className="text-white font-semibold">#{entry.rank}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    {getAvatarUrl(entry) ? (
                      <img
                        src={getAvatarUrl(entry)!}
                        alt={entry.username}
                        className="w-10 h-10 rounded-full"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-sm font-bold text-white">
                        {entry.username.charAt(0).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <p className="text-white font-medium">{entry.username}</p>
                      <p className="text-xs text-gray-400">#{entry.discriminator}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-purple-900/30 text-purple-300">
                    Level {entry.level}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="text-white font-mono">{formatXP(entry.total_xp)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {leaderboard.length === 0 && (
          <div className="px-6 py-12 text-center text-gray-400">
            No leaderboard data available
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Showing {(currentPage - 1) * itemsPerPage + 1} -{' '}
            {Math.min(currentPage * itemsPerPage, totalUsers)} of {totalUsers} users
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg font-semibold hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>

            <div className="flex items-center gap-2">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                      currentPage === pageNum
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg font-semibold hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

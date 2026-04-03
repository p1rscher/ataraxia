import { getBotStats, formatNumber } from "../lib/api";

export default async function DashboardPage() {
  // Fetch live stats
  let stats = {
    total_servers: 0,
    total_users: 0,
    total_commands: 0,
  };

  try {
    stats = await getBotStats();
  } catch (error) {
    console.error('Failed to load stats:', error);
  }

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">
          Welcome back! 👋
        </h1>
        <p className="text-gray-400">
          Here's what's happening with your bot today.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Servers */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <div className="text-3xl">🖥️</div>
            <div className="text-sm text-gray-400">Total</div>
          </div>
          <div className="text-3xl font-bold text-white mb-1">
            {formatNumber(stats.total_servers)}
          </div>
          <div className="text-gray-400 text-sm">Servers</div>
          <div className="mt-4 text-green-400 text-sm flex items-center gap-1">
            <span>↗</span>
            <span>+12% this month</span>
          </div>
        </div>

        {/* Total Users */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <div className="text-3xl">👥</div>
            <div className="text-sm text-gray-400">Total</div>
          </div>
          <div className="text-3xl font-bold text-white mb-1">
            {formatNumber(stats.total_users)}
          </div>
          <div className="text-gray-400 text-sm">Users</div>
          <div className="mt-4 text-green-400 text-sm flex items-center gap-1">
            <span>↗</span>
            <span>+8% this month</span>
          </div>
        </div>

        {/* Total Commands */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <div className="text-3xl">⚡</div>
            <div className="text-sm text-gray-400">Total</div>
          </div>
          <div className="text-3xl font-bold text-white mb-1">
            {formatNumber(stats.total_commands)}
          </div>
          <div className="text-gray-400 text-sm">Commands Used</div>
          <div className="mt-4 text-green-400 text-sm flex items-center gap-1">
            <span>↗</span>
            <span>+23% this month</span>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <a
            href="/dashboard/xp"
            className="flex items-center gap-3 p-4 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
          >
            <span className="text-2xl">⚡</span>
            <div>
              <div className="text-white font-medium">XP Settings</div>
              <div className="text-gray-400 text-sm">Configure XP system</div>
            </div>
          </a>

          <a
            href="/dashboard/multipliers"
            className="flex items-center gap-3 p-4 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
          >
            <span className="text-2xl">🎯</span>
            <div>
              <div className="text-white font-medium">Multipliers</div>
              <div className="text-gray-400 text-sm">Manage boost rates</div>
            </div>
          </a>

          <a
            href="/dashboard/leaderboard"
            className="flex items-center gap-3 p-4 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
          >
            <span className="text-2xl">🏆</span>
            <div>
              <div className="text-white font-medium">Leaderboard</div>
              <div className="text-gray-400 text-sm">View top users</div>
            </div>
          </a>

          <a
            href="/dashboard/logs"
            className="flex items-center gap-3 p-4 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
          >
            <span className="text-2xl">📝</span>
            <div>
              <div className="text-white font-medium">Logs</div>
              <div className="text-gray-400 text-sm">Configure logging</div>
            </div>
          </a>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-4">Recent Activity</h2>
        <div className="space-y-4">
          <div className="flex items-center gap-4 p-4 bg-gray-700 rounded-lg">
            <div className="text-2xl">🎉</div>
            <div className="flex-1">
              <div className="text-white font-medium">User leveled up</div>
              <div className="text-gray-400 text-sm">@John reached level 25</div>
            </div>
            <div className="text-gray-400 text-sm">2 min ago</div>
          </div>

          <div className="flex items-center gap-4 p-4 bg-gray-700 rounded-lg">
            <div className="text-2xl">📊</div>
            <div className="flex-1">
              <div className="text-white font-medium">XP settings updated</div>
              <div className="text-gray-400 text-sm">Cooldown changed to 60 seconds</div>
            </div>
            <div className="text-gray-400 text-sm">1 hour ago</div>
          </div>

          <div className="flex items-center gap-4 p-4 bg-gray-700 rounded-lg">
            <div className="text-2xl">🎯</div>
            <div className="flex-1">
              <div className="text-white font-medium">Multiplier added</div>
              <div className="text-gray-400 text-sm">2x XP in #general</div>
            </div>
            <div className="text-gray-400 text-sm">3 hours ago</div>
          </div>
        </div>
      </div>
    </div>
  );
}

import Link from "next/link";
import { getBotStats, formatNumber } from "./lib/api";

export default async function Home() {
  // Fetch live stats from the bot
  let stats = {
    total_servers: 0,
    total_users: 0,
    total_commands: 0,
  };

  try {
    stats = await getBotStats();
  } catch (error) {
    console.error('Failed to load stats:', error);
    // Use placeholder values on error
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      {/* Hero Section */}
      <div className="container mx-auto px-6 py-24">
        <div className="flex flex-col items-center text-center">
          {/* Logo/Title */}
          <div className="mb-8">
            <h1 className="text-7xl font-bold bg-gradient-to-r from-purple-400 via-pink-500 to-blue-500 bg-clip-text text-transparent mb-4">
              Ataraxia
            </h1>
            <p className="text-2xl text-gray-300">
              The Ultimate Discord Bot Dashboard
            </p>
          </div>

          {/* Description */}
          <p className="text-lg text-gray-400 max-w-2xl mb-12">
            Manage your Discord server with ease. Configure XP systems, multipliers, 
            logging, and more - all in one beautiful dashboard.
          </p>

          {/* CTA Buttons */}
          <div className="flex gap-4 mb-20">
            <Link
              href="/dashboard"
              className="px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg text-white font-semibold hover:scale-105 transition-transform shadow-lg hover:shadow-purple-500/50"
            >
              Get Started
            </Link>
            <Link
              href="/docs"
              className="px-8 py-4 bg-gray-800 rounded-lg text-white font-semibold hover:bg-gray-700 transition-colors border border-gray-700"
            >
              Documentation
            </Link>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-6xl">
            {/* Feature 1: XP System */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-purple-500 transition-colors">
              <div className="text-4xl mb-4">⚡</div>
              <h3 className="text-xl font-bold text-white mb-2">XP System</h3>
              <p className="text-gray-400">
                Fully customizable XP and leveling system with configurable rewards and cooldowns
              </p>
            </div>

            {/* Feature 2: Multipliers */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-pink-500 transition-colors">
              <div className="text-4xl mb-4">🎯</div>
              <h3 className="text-xl font-bold text-white mb-2">Multipliers</h3>
              <p className="text-gray-400">
                Set channel and role-based XP multipliers to boost engagement in specific areas
              </p>
            </div>

            {/* Feature 3: Leaderboard */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-blue-500 transition-colors">
              <div className="text-4xl mb-4">🏆</div>
              <h3 className="text-xl font-bold text-white mb-2">Leaderboards</h3>
              <p className="text-gray-400">
                Track top members with beautiful, real-time leaderboards and stats
              </p>
            </div>

            {/* Feature 4: Logging */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-green-500 transition-colors">
              <div className="text-4xl mb-4">📝</div>
              <h3 className="text-xl font-bold text-white mb-2">Smart Logging</h3>
              <p className="text-gray-400">
                Comprehensive logging for messages, voice activity, and level-ups
              </p>
            </div>

            {/* Feature 5: Analytics */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-yellow-500 transition-colors">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-xl font-bold text-white mb-2">Analytics</h3>
              <p className="text-gray-400">
                Deep insights into server activity, user engagement, and growth trends
              </p>
            </div>

            {/* Feature 6: Easy Setup */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-8 border border-gray-700 hover:border-orange-500 transition-colors">
              <div className="text-4xl mb-4">🚀</div>
              <h3 className="text-xl font-bold text-white mb-2">Easy Setup</h3>
              <p className="text-gray-400">
                Intuitive interface with real-time updates and instant configuration changes
              </p>
            </div>
          </div>

          {/* Stats Section - NOW WITH LIVE DATA! */}
          <div className="mt-20 grid grid-cols-1 md:grid-cols-4 gap-8 w-full max-w-4xl">
            <div className="text-center">
              <div className="text-4xl font-bold text-purple-400">
                {formatNumber(stats.total_servers)}
              </div>
              <div className="text-gray-400 mt-2">Servers</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-pink-400">
                {formatNumber(stats.total_users)}
              </div>
              <div className="text-gray-400 mt-2">Users</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-blue-400">
                {formatNumber(stats.total_commands)}
              </div>
              <div className="text-gray-400 mt-2">Commands</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-400">24/7</div>
              <div className="text-gray-400 mt-2">Uptime</div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-20">
        <div className="container mx-auto px-6 py-8">
          <div className="flex flex-col md:flex-row justify-between items-center text-gray-400 text-sm">
            <div>© 2025 Ataraxia Bot. All rights reserved.</div>
            <div className="flex gap-6 mt-4 md:mt-0">
              <Link href="/privacy" className="hover:text-white transition-colors">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-white transition-colors">
                Terms
              </Link>
              <Link href="/docs" className="hover:text-white transition-colors">
                Docs
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

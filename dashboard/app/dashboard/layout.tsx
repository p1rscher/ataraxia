'use client';

import Link from "next/link";
import { LoginButton } from "../components/LoginButton";
import { ServerProvider } from "../contexts/ServerContext";
import ServerSelector from "../components/ServerSelector";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ServerProvider>
      <div className="min-h-screen bg-gray-900 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700 fixed h-full">
        <div className="p-6">
          {/* Logo */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
              Ataraxia
            </h1>
            <p className="text-gray-400 text-sm">Dashboard</p>
          </div>

          {/* Navigation */}
          <nav className="space-y-2">
            <Link
              href="/dashboard"
              className="flex items-center gap-3 px-4 py-3 rounded-lg bg-purple-600 text-white"
            >
              <span className="text-xl">🏠</span>
              <span className="font-medium">Overview</span>
            </Link>
            
            <Link
              href="/dashboard/xp"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">⚡</span>
              <span className="font-medium">XP Settings</span>
            </Link>

            <Link
              href="/dashboard/multipliers"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">🎯</span>
              <span className="font-medium">Multipliers</span>
            </Link>

            <Link
              href="/dashboard/leaderboard"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">🏆</span>
              <span className="font-medium">Leaderboard</span>
            </Link>

            <Link
              href="/dashboard/logs"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">📝</span>
              <span className="font-medium">Logging</span>
            </Link>

            <Link
              href="/dashboard/analytics"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">📊</span>
              <span className="font-medium">Analytics</span>
            </Link>

            <Link
              href="/dashboard/profile"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">👤</span>
              <span className="font-medium">My Profile</span>
            </Link>
          </nav>

          {/* Settings */}
          <div className="absolute bottom-6 left-6 right-6">
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <span className="text-xl">⚙️</span>
              <span className="font-medium">Settings</span>
            </Link>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 flex-1">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Dashboard</h2>
              <p className="text-gray-400 text-sm">Manage your Discord server</p>
            </div>
            
            {/* User/Server Selector */}
            <div className="flex items-center gap-4">
              <ServerSelector />
              
              <LoginButton />
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
    </ServerProvider>
  );
}

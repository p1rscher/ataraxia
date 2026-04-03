'use client';

import { useState } from 'react';
import { useServer } from '../../contexts/ServerContext';
import LevelRolesTab from './components/LevelRolesTab';
import AutoRolesTab from './components/AutoRolesTab';
import ParentRolesTab from './components/ParentRolesTab';
import VerificationTab from './components/VerificationTab';
import MessagesTab from './components/MessagesTab';

type TabType = 'level-roles' | 'auto-roles' | 'parent-roles' | 'verification' | 'messages';

export default function SettingsPage() {
  const { selectedServer } = useServer();
  const [activeTab, setActiveTab] = useState<TabType>('level-roles');

  if (!selectedServer) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-20">
            <div className="text-6xl mb-4">🔧</div>
            <h2 className="text-2xl font-bold text-white mb-2">No Server Selected</h2>
            <p className="text-gray-400">Please select a server from the dropdown to configure settings</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">⚙️ Server Settings</h1>
          <p className="text-gray-400">Configure roles, verification, and welcome messages</p>
        </div>

        {/* Tab Navigation */}
        <div className="bg-gray-800/50 rounded-lg p-2 mb-6 flex gap-2 flex-wrap">
          <button
            onClick={() => setActiveTab('level-roles')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'level-roles'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            📊 Level Roles
          </button>
          <button
            onClick={() => setActiveTab('auto-roles')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'auto-roles'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            🎭 Auto Roles
          </button>
          <button
            onClick={() => setActiveTab('parent-roles')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'parent-roles'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            👑 Parent Roles
          </button>
          <button
            onClick={() => setActiveTab('verification')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'verification'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            ✅ Verification
          </button>
          <button
            onClick={() => setActiveTab('messages')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'messages'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            💬 Messages
          </button>
        </div>

        {/* Tab Content */}
        <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700/50">
          {activeTab === 'level-roles' && <LevelRolesTab selectedServer={selectedServer?.id || null} />}
          {activeTab === 'auto-roles' && <AutoRolesTab selectedServer={selectedServer?.id || null} />}
          {activeTab === 'parent-roles' && <ParentRolesTab selectedServer={selectedServer?.id || null} />}
          {activeTab === 'verification' && <VerificationTab selectedServer={selectedServer?.id || null} />}
          {activeTab === 'messages' && <MessagesTab selectedServer={selectedServer?.id || null} />}
        </div>
      </div>
    </div>
  );
}

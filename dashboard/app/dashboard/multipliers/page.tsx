'use client';

import { useState, useEffect } from 'react';
import { useServer } from '../../contexts/ServerContext';

interface ChannelMultiplier {
  channel_id: string;
  channel_name: string;
  multiplier: number;
}

interface RoleMultiplier {
  role_id: string;
  role_name: string;
  multiplier: number;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

interface DiscordRole {
  id: string;
  name: string;
  color: number;
}

type TabType = 'channels' | 'roles';

export default function MultipliersPage() {
  const { selectedServer } = useServer();
  const [activeTab, setActiveTab] = useState<TabType>('channels');
  const [channelMultipliers, setChannelMultipliers] = useState<ChannelMultiplier[]>([]);
  const [roleMultipliers, setRoleMultipliers] = useState<RoleMultiplier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Available channels and roles
  const [availableChannels, setAvailableChannels] = useState<DiscordChannel[]>([]);
  const [availableRoles, setAvailableRoles] = useState<DiscordRole[]>([]);
  
  // Add Multiplier Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newMultiplier, setNewMultiplier] = useState({ id: '', name: '', value: 1.0 });

  useEffect(() => {
    if (selectedServer) {
      fetchMultipliers();
      fetchGuildData();
    }
  }, [selectedServer, activeTab]);

  const fetchGuildData = async () => {
    if (!selectedServer) return;

    try {
      const type = activeTab === 'channels' ? 'channels' : 'roles';
      const response = await fetch(`/api/guild-data?guildId=${selectedServer.id}&type=${type}`);
      
      if (response.ok) {
        const data = await response.json();
        if (activeTab === 'channels') {
          setAvailableChannels(data);
        } else {
          setAvailableRoles(data);
        }
      }
    } catch (error) {
      console.error('Error fetching guild data:', error);
    }
  };

  const fetchMultipliers = async () => {
    if (!selectedServer) return;

    try {
      setIsLoading(true);
      const endpoint = activeTab === 'channels' 
        ? `/api/multipliers/channels?guildId=${selectedServer.id}`
        : `/api/multipliers/roles?guildId=${selectedServer.id}`;
      
      const response = await fetch(endpoint);
      
      if (response.ok) {
        const data = await response.json();
        if (activeTab === 'channels') {
          setChannelMultipliers(data);
        } else {
          setRoleMultipliers(data);
        }
      }
    } catch (error) {
      console.error('Error fetching multipliers:', error);
      setMessage({ type: 'error', text: 'Failed to load multipliers' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!selectedServer || !newMultiplier.id) return;

    try {
      const endpoint = activeTab === 'channels' 
        ? '/api/multipliers/channels'
        : '/api/multipliers/roles';
      
      const body = activeTab === 'channels'
        ? { guildId: selectedServer.id, channel_id: newMultiplier.id, multiplier: newMultiplier.value }
        : { guildId: selectedServer.id, role_id: newMultiplier.id, multiplier: newMultiplier.value };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Multiplier added successfully!' });
        setIsAddModalOpen(false);
        setNewMultiplier({ id: '', name: '', value: 1.0 });
        fetchMultipliers();
        setTimeout(() => setMessage(null), 3000);
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Failed to add multiplier' });
      }
    } catch (error) {
      console.error('Error adding multiplier:', error);
      setMessage({ type: 'error', text: 'Failed to add multiplier' });
    }
  };

  const handleDelete = async (id: string) => {
    if (!selectedServer) return;

    try {
      const endpoint = activeTab === 'channels'
        ? `/api/multipliers/channels?guildId=${selectedServer.id}&channelId=${id}`
        : `/api/multipliers/roles?guildId=${selectedServer.id}&roleId=${id}`;

      const response = await fetch(endpoint, { method: 'DELETE' });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Multiplier removed successfully!' });
        fetchMultipliers();
        setTimeout(() => setMessage(null), 3000);
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Failed to remove multiplier' });
      }
    } catch (error) {
      console.error('Error removing multiplier:', error);
      setMessage({ type: 'error', text: 'Failed to remove multiplier' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Please select a server to manage multipliers</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">XP Multipliers</h1>
        <p className="text-gray-400">Configure XP boost multipliers for channels and roles</p>
      </div>

      {/* Success/Error Message */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-900/20 border border-green-700 text-green-400'
              : 'bg-red-900/20 border border-red-700 text-red-400'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="mb-6 flex gap-2 border-b border-gray-700">
        <button
          onClick={() => setActiveTab('channels')}
          className={`px-6 py-3 font-semibold transition-colors ${
            activeTab === 'channels'
              ? 'text-purple-400 border-b-2 border-purple-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          📢 Channels
        </button>
        <button
          onClick={() => setActiveTab('roles')}
          className={`px-6 py-3 font-semibold transition-colors ${
            activeTab === 'roles'
              ? 'text-purple-400 border-b-2 border-purple-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          🎭 Roles
        </button>
      </div>

      {/* Add Button */}
      <div className="mb-6">
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-pink-700 transition-colors"
        >
          + Add {activeTab === 'channels' ? 'Channel' : 'Role'} Multiplier
        </button>
      </div>

      {/* Multipliers List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-900/50">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                  {activeTab === 'channels' ? 'Channel' : 'Role'}
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                  Multiplier
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-gray-300">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {activeTab === 'channels' ? (
                channelMultipliers.length > 0 ? (
                  channelMultipliers.map((item) => (
                    <tr key={item.channel_id} className="hover:bg-gray-700/50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">#</span>
                          <span className="text-white font-medium">{item.channel_name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-purple-900/30 text-purple-300">
                          {item.multiplier}x
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(item.channel_id)}
                          className="text-red-400 hover:text-red-300 font-semibold transition-colors"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="px-6 py-12 text-center text-gray-400">
                      No channel multipliers configured
                    </td>
                  </tr>
                )
              ) : (
                roleMultipliers.length > 0 ? (
                  roleMultipliers.map((item) => (
                    <tr key={item.role_id} className="hover:bg-gray-700/50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">@</span>
                          <span className="text-white font-medium">{item.role_name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-purple-900/30 text-purple-300">
                          {item.multiplier}x
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(item.role_id)}
                          className="text-red-400 hover:text-red-300 font-semibold transition-colors"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="px-6 py-12 text-center text-gray-400">
                      No role multipliers configured
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4">
              Add {activeTab === 'channels' ? 'Channel' : 'Role'} Multiplier
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  {activeTab === 'channels' ? 'Select Channel' : 'Select Role'}
                </label>
                <select
                  value={newMultiplier.id}
                  onChange={(e) => {
                    const selectedId = e.target.value;
                    const selectedItem = activeTab === 'channels'
                      ? availableChannels.find(c => c.id === selectedId)
                      : availableRoles.find(r => r.id === selectedId);
                    setNewMultiplier({
                      id: selectedId,
                      name: selectedItem?.name || '',
                      value: newMultiplier.value
                    });
                  }}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="">-- Select {activeTab === 'channels' ? 'Channel' : 'Role'} --</option>
                  {activeTab === 'channels'
                    ? availableChannels.map((channel) => (
                        <option key={channel.id} value={channel.id}>
                          {channel.type === 2 ? '🔊' : '#'} {channel.name}
                        </option>
                      ))
                    : availableRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          @{role.name}
                        </option>
                      ))
                  }
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Multiplier
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  value={newMultiplier.value}
                  onChange={(e) => setNewMultiplier({ ...newMultiplier, value: parseFloat(e.target.value) || 1.0 })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                />
                <p className="text-sm text-gray-400 mt-1">
                  Example: 2.0 = double XP, 0.5 = half XP
                </p>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  setNewMultiplier({ id: '', name: '', value: 1.0 });
                }}
                className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg font-semibold hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!newMultiplier.id}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-pink-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

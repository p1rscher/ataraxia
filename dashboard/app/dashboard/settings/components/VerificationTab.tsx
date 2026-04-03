'use client';

import { useState, useEffect } from 'react';

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

interface VerificationTabProps {
  selectedServer: string | null;
}

export default function VerificationTab({ selectedServer }: VerificationTabProps) {
  const [config, setConfig] = useState({
    enabled: false,
    channel_id: '',
    role_id: '',
    title: 'Verification',
    message: 'React with ✅ to get verified and access the server.',
    footer: 'Welcome to our community!',
  });
  const [availableChannels, setAvailableChannels] = useState<DiscordChannel[]>([]);
  const [availableRoles, setAvailableRoles] = useState<DiscordRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (selectedServer) {
      fetchConfig();
      fetchChannels();
      fetchRoles();
    }
  }, [selectedServer]);

  const fetchConfig = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/verification?guildId=${selectedServer}`);
      if (!response.ok) throw new Error('Failed to fetch config');
      const data = await response.json();
      setConfig(data);
    } catch (error) {
      console.error('Error fetching verification config:', error);
      setMessage({ type: 'error', text: 'Failed to load configuration' });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchChannels = async () => {
    try {
      const response = await fetch(`/api/guild-data?guildId=${selectedServer}&type=channels`);
      if (!response.ok) throw new Error('Failed to fetch channels');
      const data = await response.json();
      setAvailableChannels(data.filter((ch: DiscordChannel) => ch.type === 0));
    } catch (error) {
      console.error('Error fetching channels:', error);
    }
  };

  const fetchRoles = async () => {
    try {
      const response = await fetch(`/api/guild-data?guildId=${selectedServer}&type=roles`);
      if (!response.ok) throw new Error('Failed to fetch roles');
      const data = await response.json();
      setAvailableRoles(data);
    } catch (error) {
      console.error('Error fetching roles:', error);
    }
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/verification', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          ...config,
        }),
      });

      if (!response.ok) throw new Error('Failed to save config');

      setMessage({ type: 'success', text: 'Verification settings saved successfully' });
    } catch (error) {
      console.error('Error saving verification config:', error);
      setMessage({ type: 'error', text: 'Failed to save settings' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Please select a server to configure verification</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-4 rounded-lg ${message.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
          {message.text}
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12">
          <p className="text-gray-400">Loading...</p>
        </div>
      ) : (
        <>
          <div className="bg-gray-800/50 rounded-lg p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Enable Verification</h3>
                <p className="text-gray-400 text-sm">Require new members to verify before accessing the server</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-purple-500 peer-checked:to-pink-500"></div>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Verification Channel</label>
              <select
                value={config.channel_id}
                onChange={(e) => setConfig({ ...config, channel_id: e.target.value })}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              >
                <option value="">Select channel...</option>
                {availableChannels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Verified Role</label>
              <select
                value={config.role_id}
                onChange={(e) => setConfig({ ...config, role_id: e.target.value })}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              >
                <option value="">Select role...</option>
                {availableRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Embed Title</label>
              <input
                type="text"
                value={config.title}
                onChange={(e) => setConfig({ ...config, title: e.target.value })}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Verification Message</label>
              <textarea
                value={config.message}
                onChange={(e) => setConfig({ ...config, message: e.target.value })}
                rows={3}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Embed Footer</label>
              <input
                type="text"
                value={config.footer}
                onChange={(e) => setConfig({ ...config, footer: e.target.value })}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              />
            </div>
          </div>

          <button
            onClick={handleSave}
            className="w-full px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
          >
            💾 Save Verification Settings
          </button>
        </>
      )}
    </div>
  );
}

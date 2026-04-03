'use client';

import { useState, useEffect } from 'react';

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

interface MessagesTabProps {
  selectedServer: string | null;
}

export default function MessagesTab({ selectedServer }: MessagesTabProps) {
  const [welcomeConfig, setWelcomeConfig] = useState({
    enabled: false,
    channel_id: '',
    message: 'Welcome {user} to **{server}**! 🎉',
    embed_enabled: false,
    embed_title: '',
    embed_description: '',
    embed_color: '#7289da',
  });
  const [goodbyeConfig, setGoodbyeConfig] = useState({
    enabled: false,
    channel_id: '',
    message: '{user} just left the server.',
  });
  const [availableChannels, setAvailableChannels] = useState<DiscordChannel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (selectedServer) {
      fetchWelcomeConfig();
      fetchGoodbyeConfig();
      fetchChannels();
    }
  }, [selectedServer]);

  const fetchWelcomeConfig = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/welcome-messages?guildId=${selectedServer}&type=welcome`);
      if (!response.ok) throw new Error('Failed to fetch welcome config');
      const data = await response.json();
      setWelcomeConfig(data);
    } catch (error) {
      console.error('Error fetching welcome config:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchGoodbyeConfig = async () => {
    try {
      const response = await fetch(`/api/welcome-messages?guildId=${selectedServer}&type=goodbye`);
      if (!response.ok) throw new Error('Failed to fetch goodbye config');
      const data = await response.json();
      setGoodbyeConfig(data);
    } catch (error) {
      console.error('Error fetching goodbye config:', error);
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

  const handleSave = async () => {
    try {
      const welcomeResponse = await fetch('/api/welcome-messages', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          type: 'welcome',
          ...welcomeConfig,
        }),
      });

      const goodbyeResponse = await fetch('/api/welcome-messages', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          type: 'goodbye',
          ...goodbyeConfig,
        }),
      });

      if (!welcomeResponse.ok || !goodbyeResponse.ok) {
        throw new Error('Failed to save configs');
      }

      setMessage({ type: 'success', text: 'Message settings saved successfully' });
    } catch (error) {
      console.error('Error saving message configs:', error);
      setMessage({ type: 'error', text: 'Failed to save settings' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Please select a server to configure messages</p>
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
          {/* Welcome Messages */}
          <div className="bg-gray-800/50 rounded-lg p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Welcome Messages</h3>
                <p className="text-gray-400 text-sm">Send a message when new members join</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={welcomeConfig.enabled}
                  onChange={(e) => setWelcomeConfig({ ...welcomeConfig, enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-purple-500 peer-checked:to-pink-500"></div>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Welcome Channel</label>
              <select
                value={welcomeConfig.channel_id}
                onChange={(e) => setWelcomeConfig({ ...welcomeConfig, channel_id: e.target.value })}
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
              <label className="block text-sm font-medium text-gray-300 mb-2">Welcome Message</label>
              <textarea
                value={welcomeConfig.message}
                onChange={(e) => setWelcomeConfig({ ...welcomeConfig, message: e.target.value })}
                rows={3}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                placeholder="Use {user}, {server}, {member_count}"
              />
              <p className="text-gray-500 text-sm mt-2">
                Available placeholders: {'{user}'}, {'{server}'}, {'{member_count}'}
              </p>
            </div>
          </div>

          {/* Goodbye Messages */}
          <div className="bg-gray-800/50 rounded-lg p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Goodbye Messages</h3>
                <p className="text-gray-400 text-sm">Send a message when members leave</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={goodbyeConfig.enabled}
                  onChange={(e) => setGoodbyeConfig({ ...goodbyeConfig, enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-purple-500 peer-checked:to-pink-500"></div>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Goodbye Channel</label>
              <select
                value={goodbyeConfig.channel_id}
                onChange={(e) => setGoodbyeConfig({ ...goodbyeConfig, channel_id: e.target.value })}
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
              <label className="block text-sm font-medium text-gray-300 mb-2">Goodbye Message</label>
              <textarea
                value={goodbyeConfig.message}
                onChange={(e) => setGoodbyeConfig({ ...goodbyeConfig, message: e.target.value })}
                rows={3}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                placeholder="Use {user}, {server}"
              />
              <p className="text-gray-500 text-sm mt-2">
                Available placeholders: {'{user}'}, {'{server}'}
              </p>
            </div>
          </div>

          <button
            onClick={handleSave}
            className="w-full px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
          >
            💾 Save Message Settings
          </button>
        </>
      )}
    </div>
  );
}

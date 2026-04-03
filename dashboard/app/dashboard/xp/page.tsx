'use client';

import { useState, useEffect } from 'react';
import { useServer } from '../../contexts/ServerContext';

interface XPSettings {
  message_xp_min: number;
  message_xp_max: number;
  voice_xp_min: number;
  voice_xp_max: number;
  message_cooldown: number;
  voice_interval: number;
}

interface VoiceXPRequirements {
  require_non_afk: boolean;
  require_non_deaf: boolean;
  require_non_muted: boolean;
  require_non_alone: boolean;
}

export default function XPSettingsPage() {
  const { selectedServer } = useServer();
  const [settings, setSettings] = useState<XPSettings>({
    message_xp_min: 15,
    message_xp_max: 25,
    voice_xp_min: 10,
    voice_xp_max: 20,
    message_cooldown: 60,
    voice_interval: 60,
  });
  const [requirements, setRequirements] = useState<VoiceXPRequirements>({
    require_non_afk: true,
    require_non_deaf: true,
    require_non_muted: false,
    require_non_alone: true,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (selectedServer) {
      fetchSettings();
    }
  }, [selectedServer]);

  const fetchSettings = async () => {
    if (!selectedServer) return;

    try {
      setIsLoading(true);
      const [settingsResponse, requirementsResponse] = await Promise.all([
        fetch(`/api/xp/settings?guildId=${selectedServer.id}`),
        fetch(`/api/voicexp/requirements?guildId=${selectedServer.id}`)
      ]);
      
      if (settingsResponse.ok) {
        const data = await settingsResponse.json();
        setSettings(data);
      }

      if (requirementsResponse.ok) {
        const data = await requirementsResponse.json();
        setRequirements(data);
      }
    } catch (error) {
      console.error('Error fetching XP settings:', error);
      setMessage({ type: 'error', text: 'Failed to load XP settings' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedServer) return;

    // Validation
    if (settings.message_xp_min > settings.message_xp_max) {
      setMessage({ type: 'error', text: 'Message XP Min must be ≤ Max' });
      return;
    }

    if (settings.voice_xp_min > settings.voice_xp_max) {
      setMessage({ type: 'error', text: 'Voice XP Min must be ≤ Max' });
      return;
    }

    try {
      setIsSaving(true);
      setMessage(null);

      const [settingsResponse, requirementsResponse] = await Promise.all([
        fetch('/api/xp/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            guildId: selectedServer.id,
            ...settings,
          }),
        }),
        fetch('/api/voicexp/requirements', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            guildId: selectedServer.id,
            ...requirements,
          }),
        })
      ]);

      if (settingsResponse.ok && requirementsResponse.ok) {
        setMessage({ type: 'success', text: 'Settings saved successfully!' });
        setTimeout(() => setMessage(null), 3000);
      } else {
        const errorData = !settingsResponse.ok 
          ? await settingsResponse.json() 
          : await requirementsResponse.json();
        setMessage({ type: 'error', text: errorData.error || 'Failed to save settings' });
      }
    } catch (error) {
      console.error('Error saving XP settings:', error);
      setMessage({ type: 'error', text: 'Failed to save settings' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleInputChange = (field: keyof XPSettings, value: number) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  const handleRequirementToggle = (field: keyof VoiceXPRequirements) => {
    setRequirements((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  if (!selectedServer) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Please select a server to configure XP settings</p>
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
    <div className="max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">XP Settings</h1>
        <p className="text-gray-400">Configure experience points and cooldown settings</p>
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

      <div className="grid gap-6">
        {/* Message XP Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">💬</span>
            Message XP
          </h2>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Minimum XP per Message
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={settings.message_xp_min}
                onChange={(e) => handleInputChange('message_xp_min', parseInt(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Maximum XP per Message
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={settings.message_xp_max}
                onChange={(e) => handleInputChange('message_xp_max', parseInt(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Message Cooldown (seconds)
            </label>
            <input
              type="number"
              min="0"
              max="3600"
              value={settings.message_cooldown}
              onChange={(e) => handleInputChange('message_cooldown', parseInt(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
            />
            <p className="text-sm text-gray-400 mt-1">
              Users can earn message XP once every {settings.message_cooldown} seconds
            </p>
          </div>
        </div>

        {/* Voice XP Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">🎤</span>
            Voice XP
          </h2>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Minimum XP per Interval
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={settings.voice_xp_min}
                onChange={(e) => handleInputChange('voice_xp_min', parseInt(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Maximum XP per Interval
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={settings.voice_xp_max}
                onChange={(e) => handleInputChange('voice_xp_max', parseInt(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Voice Interval (seconds)
            </label>
            <input
              type="number"
              min="1"
              max="3600"
              value={settings.voice_interval}
              onChange={(e) => handleInputChange('voice_interval', parseInt(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
            />
            <p className="text-sm text-gray-400 mt-1">
              Users earn voice XP every {settings.voice_interval} seconds
            </p>
          </div>
        </div>

        {/* Voice XP Requirements */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">⚙️</span>
            Voice XP Requirements
          </h2>
          <p className="text-gray-400 text-sm mb-6">
            Configure conditions for earning voice XP. Users must meet all enabled requirements.
          </p>
          
          <div className="space-y-4">
            {/* Require Non-AFK */}
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🟢</span>
                <div>
                  <p className="text-white font-medium">User must not be AFK</p>
                  <p className="text-gray-400 text-sm">Users in AFK channel won't earn XP</p>
                </div>
              </div>
              <button
                onClick={() => handleRequirementToggle('require_non_afk')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  requirements.require_non_afk ? 'bg-purple-600' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    requirements.require_non_afk ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Require Non-Deaf */}
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🔇</span>
                <div>
                  <p className="text-white font-medium">User must not be deafened</p>
                  <p className="text-gray-400 text-sm">Server-deafened users won't earn XP</p>
                </div>
              </div>
              <button
                onClick={() => handleRequirementToggle('require_non_deaf')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  requirements.require_non_deaf ? 'bg-purple-600' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    requirements.require_non_deaf ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Require Non-Muted */}
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🔇</span>
                <div>
                  <p className="text-white font-medium">User must not be muted</p>
                  <p className="text-gray-400 text-sm">Server-muted users won't earn XP</p>
                </div>
              </div>
              <button
                onClick={() => handleRequirementToggle('require_non_muted')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  requirements.require_non_muted ? 'bg-purple-600' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    requirements.require_non_muted ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Require Non-Alone */}
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">👥</span>
                <div>
                  <p className="text-white font-medium">User must not be alone</p>
                  <p className="text-gray-400 text-sm">Users alone in voice channel won't earn XP</p>
                </div>
              </div>
              <button
                onClick={() => handleRequirementToggle('require_non_alone')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  requirements.require_non_alone ? 'bg-purple-600' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    requirements.require_non_alone ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="mt-4 p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
            <p className="text-blue-300 text-sm flex items-start gap-2">
              <span className="text-lg">💡</span>
              <span>
                <strong>Tip:</strong> Users must meet all enabled requirements to earn voice XP. 
                Disable requirements to make earning XP easier.
              </span>
            </p>
          </div>
        </div>

        {/* XP Preview */}
        <div className="bg-gradient-to-r from-purple-900/20 to-pink-900/20 rounded-lg p-6 border border-purple-700/50">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">📊</span>
            Preview
          </h2>
          
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-300 mb-2">💬 Message XP Range:</p>
              <p className="text-white font-mono text-lg">
                {settings.message_xp_min} - {settings.message_xp_max} XP
              </p>
            </div>
            
            <div>
              <p className="text-gray-300 mb-2">🎤 Voice XP Range:</p>
              <p className="text-white font-mono text-lg">
                {settings.voice_xp_min} - {settings.voice_xp_max} XP
              </p>
            </div>

            <div>
              <p className="text-gray-300 mb-2">⏱️ Message Cooldown:</p>
              <p className="text-white font-mono text-lg">
                {settings.message_cooldown}s
              </p>
            </div>

            <div>
              <p className="text-gray-300 mb-2">⏱️ Voice Interval:</p>
              <p className="text-white font-mono text-lg">
                {settings.voice_interval}s
              </p>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end gap-4">
          <button
            onClick={() => fetchSettings()}
            disabled={isLoading || isSaving}
            className="px-6 py-3 rounded-lg bg-gray-700 text-white font-semibold hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset
          </button>
          
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-6 py-3 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold hover:from-purple-700 hover:to-pink-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                Saving...
              </>
            ) : (
              <>
                <span>💾</span>
                Save Changes
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

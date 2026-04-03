'use client';

import { useState, useEffect } from 'react';
import { Dialog } from '@headlessui/react';

interface LevelRole {
  level: number;
  role_id: string;
  role_name: string;
}

interface DiscordRole {
  id: string;
  name: string;
  color: number;
}

interface LevelRolesTabProps {
  selectedServer: string | null;
}

export default function LevelRolesTab({ selectedServer }: LevelRolesTabProps) {
  const [levelRoles, setLevelRoles] = useState<LevelRole[]>([]);
  const [availableRoles, setAvailableRoles] = useState<DiscordRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newLevelRole, setNewLevelRole] = useState({ level: 1, role_id: '', role_name: '' });

  useEffect(() => {
    if (selectedServer) {
      fetchLevelRoles();
      fetchRoles();
    }
  }, [selectedServer]);

  const fetchLevelRoles = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/level-roles?guildId=${selectedServer}`);
      if (!response.ok) throw new Error('Failed to fetch level roles');
      const data = await response.json();
      setLevelRoles(data);
    } catch (error) {
      console.error('Error fetching level roles:', error);
      setMessage({ type: 'error', text: 'Failed to load level roles' });
    } finally {
      setIsLoading(false);
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

  const handleAddLevelRole = async () => {
    if (!newLevelRole.role_id || newLevelRole.level < 1) {
      setMessage({ type: 'error', text: 'Please select a role and enter a valid level' });
      return;
    }

    try {
      const selectedRole = availableRoles.find(r => r.id === newLevelRole.role_id);
      const response = await fetch('/api/level-roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          level: newLevelRole.level,
          roleId: newLevelRole.role_id,
          roleName: selectedRole?.name || '',
        }),
      });

      if (!response.ok) throw new Error('Failed to add level role');

      setMessage({ type: 'success', text: 'Level role added successfully' });
      setIsAddModalOpen(false);
      setNewLevelRole({ level: 1, role_id: '', role_name: '' });
      fetchLevelRoles();
    } catch (error) {
      console.error('Error adding level role:', error);
      setMessage({ type: 'error', text: 'Failed to add level role' });
    }
  };

  const handleDeleteLevelRole = async (level: number, roleId: string) => {
    try {
      const response = await fetch(
        `/api/level-roles?guildId=${selectedServer}&level=${level}&roleId=${roleId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete level role');

      setMessage({ type: 'success', text: 'Level role deleted successfully' });
      fetchLevelRoles();
    } catch (error) {
      console.error('Error deleting level role:', error);
      setMessage({ type: 'error', text: 'Failed to delete level role' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Please select a server to configure level roles</p>
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

      <div className="flex justify-between items-center">
        <p className="text-gray-400">Automatically assign roles when users reach specific levels</p>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
        >
          ➕ Add Level Role
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <p className="text-gray-400">Loading...</p>
        </div>
      ) : levelRoles.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400">No level roles configured yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {levelRoles
            .sort((a, b) => a.level - b.level)
            .map((lr) => (
              <div
                key={`${lr.level}-${lr.role_id}`}
                className="bg-gray-800/50 rounded-lg p-4 flex items-center justify-between hover:bg-gray-800/70 transition"
              >
                <div className="flex items-center gap-4">
                  <div className="bg-purple-500/20 text-purple-400 px-4 py-2 rounded-lg font-semibold">
                    Level {lr.level}
                  </div>
                  <div>
                    <div className="text-white font-medium">{lr.role_name}</div>
                    <div className="text-gray-400 text-sm">ID: {lr.role_id}</div>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteLevelRole(lr.level, lr.role_id)}
                  className="text-red-400 hover:text-red-300 transition"
                >
                  🗑️ Delete
                </button>
              </div>
            ))}
        </div>
      )}

      {/* Add Level Role Modal */}
      <Dialog open={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} className="relative z-50">
        <div className="fixed inset-0 bg-black/70" aria-hidden="true" />
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <Dialog.Panel className="bg-gray-900 rounded-lg p-6 max-w-md w-full border border-gray-700">
            <Dialog.Title className="text-xl font-bold text-white mb-4">Add Level Role</Dialog.Title>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Level</label>
                <input
                  type="number"
                  min="1"
                  value={newLevelRole.level}
                  onChange={(e) => setNewLevelRole({ ...newLevelRole, level: parseInt(e.target.value) || 1 })}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Role</label>
                <select
                  value={newLevelRole.role_id}
                  onChange={(e) => {
                    const role = availableRoles.find(r => r.id === e.target.value);
                    setNewLevelRole({
                      ...newLevelRole,
                      role_id: e.target.value,
                      role_name: role?.name || '',
                    });
                  }}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                >
                  <option value="">Select a role...</option>
                  {availableRoles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleAddLevelRole}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
              >
                Add
              </button>
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  setNewLevelRole({ level: 1, role_id: '', role_name: '' });
                }}
                className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition"
              >
                Cancel
              </button>
            </div>
          </Dialog.Panel>
        </div>
      </Dialog>
    </div>
  );
}

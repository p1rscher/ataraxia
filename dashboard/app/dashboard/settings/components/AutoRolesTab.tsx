'use client';

import { useState, useEffect } from 'react';
import { Dialog } from '@headlessui/react';

interface AutoRole {
  role_id: string;
  role_name: string;
}

interface DiscordRole {
  id: string;
  name: string;
  color: number;
}

interface AutoRolesTabProps {
  selectedServer: string | null;
}

export default function AutoRolesTab({ selectedServer }: AutoRolesTabProps) {
  const [autoRoles, setAutoRoles] = useState<AutoRole[]>([]);
  const [availableRoles, setAvailableRoles] = useState<DiscordRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newAutoRole, setNewAutoRole] = useState({ role_id: '', role_name: '' });

  useEffect(() => {
    if (selectedServer) {
      fetchAutoRoles();
      fetchRoles();
    }
  }, [selectedServer]);

  const fetchAutoRoles = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/auto-roles?guildId=${selectedServer}`);
      if (!response.ok) throw new Error('Failed to fetch auto roles');
      const data = await response.json();
      setAutoRoles(data);
    } catch (error) {
      console.error('Error fetching auto roles:', error);
      setMessage({ type: 'error', text: 'Failed to load auto roles' });
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

  const handleAddAutoRole = async () => {
    if (!newAutoRole.role_id) {
      setMessage({ type: 'error', text: 'Please select a role' });
      return;
    }

    try {
      const selectedRole = availableRoles.find(r => r.id === newAutoRole.role_id);
      const response = await fetch('/api/auto-roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          roleId: newAutoRole.role_id,
          roleName: selectedRole?.name || '',
        }),
      });

      if (!response.ok) throw new Error('Failed to add auto role');

      setMessage({ type: 'success', text: 'Auto role added successfully' });
      setIsModalOpen(false);
      setNewAutoRole({ role_id: '', role_name: '' });
      fetchAutoRoles();
    } catch (error) {
      console.error('Error adding auto role:', error);
      setMessage({ type: 'error', text: 'Failed to add auto role' });
    }
  };

  const handleDeleteAutoRole = async (roleId: string) => {
    try {
      const response = await fetch(
        `/api/auto-roles?guildId=${selectedServer}&roleId=${roleId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete auto role');

      setMessage({ type: 'success', text: 'Auto role deleted successfully' });
      fetchAutoRoles();
    } catch (error) {
      console.error('Error deleting auto role:', error);
      setMessage({ type: 'error', text: 'Failed to delete auto role' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Please select a server to configure auto roles</p>
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
        <p className="text-gray-400">Automatically assign these roles to new members when they join</p>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
        >
          ➕ Add Auto Role
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <p className="text-gray-400">Loading...</p>
        </div>
      ) : autoRoles.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400">No auto roles configured yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {autoRoles.map((role) => (
            <div
              key={role.role_id}
              className="bg-gray-800/50 rounded-lg p-4 flex items-center justify-between hover:bg-gray-800/70 transition"
            >
              <div>
                <div className="text-white font-medium">{role.role_name}</div>
                <div className="text-gray-400 text-sm">ID: {role.role_id}</div>
              </div>
              <button
                onClick={() => handleDeleteAutoRole(role.role_id)}
                className="text-red-400 hover:text-red-300 transition"
              >
                🗑️ Delete
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add Auto Role Modal */}
      <Dialog open={isModalOpen} onClose={() => setIsModalOpen(false)} className="relative z-50">
        <div className="fixed inset-0 bg-black/70" aria-hidden="true" />
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <Dialog.Panel className="bg-gray-900 rounded-lg p-6 max-w-md w-full border border-gray-700">
            <Dialog.Title className="text-xl font-bold text-white mb-4">Add Auto Role</Dialog.Title>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Role</label>
                <select
                  value={newAutoRole.role_id}
                  onChange={(e) => {
                    const role = availableRoles.find(r => r.id === e.target.value);
                    setNewAutoRole({
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
                onClick={handleAddAutoRole}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
              >
                Add
              </button>
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setNewAutoRole({ role_id: '', role_name: '' });
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

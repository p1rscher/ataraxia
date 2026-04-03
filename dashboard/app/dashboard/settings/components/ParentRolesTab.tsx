'use client';

import { useState, useEffect } from 'react';
import { Dialog } from '@headlessui/react';

interface ParentRole {
  id: string;
  parent_role_id: string;
  parent_role_name: string;
  child_role_ids: string[];
  child_role_names: string[];
}

interface DiscordRole {
  id: string;
  name: string;
  color: number;
}

interface ParentRolesTabProps {
  selectedServer: string | null;
}

export default function ParentRolesTab({ selectedServer }: ParentRolesTabProps) {
  const [parentRoles, setParentRoles] = useState<ParentRole[]>([]);
  const [availableRoles, setAvailableRoles] = useState<DiscordRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedParentRole, setSelectedParentRole] = useState('');
  const [selectedChildRole, setSelectedChildRole] = useState('');

  useEffect(() => {
    if (selectedServer) {
      fetchParentRoles();
      fetchRoles();
    }
  }, [selectedServer]);

  const fetchParentRoles = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/parent-roles?guildId=${selectedServer}`);
      if (!response.ok) throw new Error('Failed to fetch parent roles');
      const data = await response.json();
      setParentRoles(data);
    } catch (error) {
      console.error('Error fetching parent roles:', error);
      setMessage({ type: 'error', text: 'Failed to load parent roles' });
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

  const handleAddParentRole = async () => {
    if (!selectedParentRole || !selectedChildRole) {
      setMessage({ type: 'error', text: 'Please select both parent and child roles' });
      return;
    }

    try {
      const parentRole = availableRoles.find(r => r.id === selectedParentRole);
      const childRole = availableRoles.find(r => r.id === selectedChildRole);

      const response = await fetch('/api/parent-roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId: selectedServer,
          parentRoleId: selectedParentRole,
          parentRoleName: parentRole?.name || '',
          childRoleId: selectedChildRole,
          childRoleName: childRole?.name || '',
        }),
      });

      if (!response.ok) throw new Error('Failed to add parent role');

      setMessage({ type: 'success', text: 'Parent role relationship added successfully' });
      setIsModalOpen(false);
      setSelectedParentRole('');
      setSelectedChildRole('');
      fetchParentRoles();
    } catch (error) {
      console.error('Error adding parent role:', error);
      setMessage({ type: 'error', text: 'Failed to add parent role' });
    }
  };

  const handleRemoveChildRole = async (parentRoleId: string, childRoleId: string) => {
    try {
      const response = await fetch(
        `/api/parent-roles?guildId=${selectedServer}&parentRoleId=${parentRoleId}&childRoleId=${childRoleId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to remove child role');

      setMessage({ type: 'success', text: 'Child role removed successfully' });
      fetchParentRoles();
    } catch (error) {
      console.error('Error removing child role:', error);
      setMessage({ type: 'error', text: 'Failed to remove child role' });
    }
  };

  if (!selectedServer) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Please select a server to configure parent roles</p>
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
        <div>
          <p className="text-gray-400">When a member has a parent role, they automatically get all child roles</p>
          <p className="text-gray-500 text-sm mt-1">Example: "Premium" role → "VIP Chat Access" + "Special Events"</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
        >
          ➕ Add Parent Role
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <p className="text-gray-400">Loading...</p>
        </div>
      ) : parentRoles.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400">No parent roles configured yet</p>
        </div>
      ) : (
        <div className="space-y-4">
          {parentRoles.map((pr) => (
            <div key={pr.id} className="bg-gray-800/50 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-purple-500/20 text-purple-400 px-4 py-2 rounded-lg font-semibold">
                    👑 {pr.parent_role_name}
                  </div>
                </div>
              </div>

              <div className="pl-8 space-y-2">
                <div className="text-gray-400 text-sm font-medium mb-2">Child Roles:</div>
                {pr.child_role_names.map((childName, idx) => (
                  <div
                    key={pr.child_role_ids[idx]}
                    className="flex items-center justify-between bg-gray-900/50 rounded-lg p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400">↳</span>
                      <span className="text-white">{childName}</span>
                    </div>
                    <button
                      onClick={() => handleRemoveChildRole(pr.parent_role_id, pr.child_role_ids[idx])}
                      className="text-red-400 hover:text-red-300 transition text-sm"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Parent Role Modal */}
      <Dialog open={isModalOpen} onClose={() => setIsModalOpen(false)} className="relative z-50">
        <div className="fixed inset-0 bg-black/70" aria-hidden="true" />
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <Dialog.Panel className="bg-gray-900 rounded-lg p-6 max-w-md w-full border border-gray-700">
            <Dialog.Title className="text-xl font-bold text-white mb-4">Add Parent Role Relationship</Dialog.Title>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Parent Role</label>
                <select
                  value={selectedParentRole}
                  onChange={(e) => setSelectedParentRole(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                >
                  <option value="">Select parent role...</option>
                  {availableRoles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Child Role</label>
                <select
                  value={selectedChildRole}
                  onChange={(e) => setSelectedChildRole(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                >
                  <option value="">Select child role...</option>
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
                onClick={handleAddParentRole}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition"
              >
                Add
              </button>
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setSelectedParentRole('');
                  setSelectedChildRole('');
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

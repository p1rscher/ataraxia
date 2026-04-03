'use client';

import { useEffect, Fragment, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { useServer } from '../contexts/ServerContext';
import { Menu, Transition } from '@headlessui/react';
import { ChevronDownIcon } from '@heroicons/react/20/solid';

export default function ServerSelector() {
  const { data: session } = useSession();
  const { selectedServer, setSelectedServer, guilds, setGuilds, isLoading, setIsLoading } = useServer();
  const hasLoadedGuilds = useRef(false);

  useEffect(() => {
    if (session && !hasLoadedGuilds.current) {
      fetchGuilds();
      hasLoadedGuilds.current = true;
    } else if (!session) {
      setGuilds([]);
      setSelectedServer(null);
      setIsLoading(false);
      hasLoadedGuilds.current = false;
    }
  }, [session]);

  const fetchGuilds = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/guilds');
      if (response.ok) {
        const data = await response.json();
        setGuilds(data);
        
        // Only set a server if none is currently selected
        if (!selectedServer && data.length > 0) {
          // Check if there's a saved server in localStorage
          const savedServerId = localStorage.getItem('selectedServerId');
          if (savedServerId) {
            const savedServer = data.find((g: any) => g.id === savedServerId);
            if (savedServer) {
              setSelectedServer(savedServer);
              return;
            }
          }
          // No saved server or not found, select first one
          setSelectedServer(data[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching guilds:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getIconUrl = (guild: { id: string; icon: string | null }) => {
    if (!guild.icon) return null;
    return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png?size=64`;
  };

  if (!session) {
    return (
      <div className="text-sm text-gray-500">
        Please sign in to select a server
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="animate-pulse bg-gray-700 h-10 w-48 rounded-lg"></div>
    );
  }

  if (guilds.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No servers found
      </div>
    );
  }

  return (
    <Menu as="div" className="relative inline-block text-left">
      <div>
        <Menu.Button className="inline-flex w-full justify-between items-center gap-x-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-gray-700 transition-colors">
          {selectedServer && (
            <div className="flex items-center gap-2">
              {getIconUrl(selectedServer) ? (
                <img
                  src={getIconUrl(selectedServer)!}
                  alt={selectedServer.name}
                  className="w-6 h-6 rounded-full"
                />
              ) : (
                <div className="w-6 h-6 rounded-full bg-purple-600 flex items-center justify-center text-xs font-bold">
                  {selectedServer.name.charAt(0).toUpperCase()}
                </div>
              )}
              <span className="max-w-[150px] truncate">{selectedServer.name}</span>
            </div>
          )}
          <ChevronDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
        </Menu.Button>
      </div>

      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute right-0 z-10 mt-2 w-64 origin-top-right rounded-lg bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none max-h-96 overflow-y-auto">
          <div className="py-1">
            {guilds.map((guild) => (
              <Menu.Item key={guild.id}>
                {({ active }) => (
                  <button
                    onClick={() => setSelectedServer(guild)}
                    className={`${
                      active ? 'bg-gray-700' : ''
                    } ${
                      selectedServer?.id === guild.id ? 'bg-gray-700/50' : ''
                    } group flex w-full items-center gap-3 px-4 py-3 text-sm text-white transition-colors`}
                  >
                    {getIconUrl(guild) ? (
                      <img
                        src={getIconUrl(guild)!}
                        alt={guild.name}
                        className="w-8 h-8 rounded-full"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-sm font-bold">
                        {guild.name.charAt(0).toUpperCase()}
                      </div>
                    )}
                    <div className="flex-1 text-left">
                      <div className="font-medium truncate">{guild.name}</div>
                      {guild.owner && (
                        <div className="text-xs text-purple-400">Owner</div>
                      )}
                    </div>
                    {selectedServer?.id === guild.id && (
                      <svg className="w-5 h-5 text-purple-500" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                )}
              </Menu.Item>
            ))}
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
  );
}

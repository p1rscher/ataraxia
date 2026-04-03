'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface Guild {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  permissions: string;
  features: string[];
}

interface ServerContextType {
  selectedServer: Guild | null;
  setSelectedServer: (server: Guild | null) => void;
  guilds: Guild[];
  setGuilds: (guilds: Guild[]) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

const ServerContext = createContext<ServerContextType | undefined>(undefined);

export function ServerProvider({ children }: { children: ReactNode }) {
  const [selectedServer, setSelectedServerState] = useState<Guild | null>(null);
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);

  // Load selected server from localStorage on client-side only
  useEffect(() => {
    if (!isInitialized) {
      const saved = localStorage.getItem('selectedServerData');
      if (saved) {
        try {
          const server = JSON.parse(saved);
          setSelectedServerState(server);
        } catch {
          // Invalid data, ignore
        }
      }
      setIsInitialized(true);
    }
  }, [isInitialized]);

  // Save selected server to localStorage whenever it changes
  const setSelectedServer = (server: Guild | null) => {
    setSelectedServerState(server);
    if (server) {
      localStorage.setItem('selectedServerId', server.id);
      localStorage.setItem('selectedServerData', JSON.stringify(server));
    } else {
      localStorage.removeItem('selectedServerId');
      localStorage.removeItem('selectedServerData');
    }
  };

  return (
    <ServerContext.Provider
      value={{
        selectedServer,
        setSelectedServer,
        guilds,
        setGuilds,
        isLoading,
        setIsLoading,
      }}
    >
      {children}
    </ServerContext.Provider>
  );
}

export function useServer() {
  const context = useContext(ServerContext);
  if (context === undefined) {
    throw new Error('useServer must be used within a ServerProvider');
  }
  return context;
}

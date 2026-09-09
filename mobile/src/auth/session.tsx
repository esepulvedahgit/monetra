import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { api, clearReadCache, setReadCacheAccount } from '../api/client';
import type { User } from '../api/types';
import { beginTokenSession, clearSessionTokens, getSessionTokens, setSessionTokens } from './sessionTokens';
import type { Tokens } from './tokens';
import { clearSessionData } from './sessionCache';

type SessionContextValue = {
  user: User | null;
  ready: boolean;
  signIn: (tokens: Tokens, user: User) => Promise<void>;
  signOut: () => Promise<void>;
  reloadUser: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | undefined>(undefined);
const userKey = 'monetra.mobile.user.v1';

export function SessionProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => { void (async () => {
    const [tokens, savedUser] = await Promise.all([getSessionTokens(), AsyncStorage.getItem(userKey)]);
    if (tokens && savedUser) {
      beginTokenSession();
      const savedAccount = JSON.parse(savedUser) as User;
      setReadCacheAccount(savedAccount.id);
      setUser(savedAccount);
    }
    setReady(true);
  })(); }, []);

  const saveUser = async (next: User | null) => {
    setUser(next);
    if (next) await AsyncStorage.setItem(userKey, JSON.stringify(next));
    else await AsyncStorage.removeItem(userKey);
  };
  const value = useMemo<SessionContextValue>(() => ({
    user, ready,
    signIn: async (tokens, account) => {
      const tokenSession = beginTokenSession();
      setReadCacheAccount(account.id);
      await clearSessionData(queryClient, clearReadCache);
      await setSessionTokens(tokenSession, tokens);
      await saveUser(account);
    },
    signOut: async () => {
      const tokenSession = beginTokenSession();
      setReadCacheAccount(null);
      await clearSessionData(queryClient, clearReadCache);
      try {
        const tokens = await getSessionTokens();
        if (tokens) await api.post('/logout', undefined, { headers: { Authorization: `Bearer ${tokens.refreshToken}` } });
      } catch { /* local logout still succeeds */ }
      await clearSessionTokens(tokenSession); await saveUser(null);
    },
    reloadUser: async () => {
      const response = await api.get<User>('/me');
      if (user && user.id !== response.data.id) await clearSessionData(queryClient, clearReadCache);
      setReadCacheAccount(response.data.id);
      await saveUser(response.data);
    },
  }), [queryClient, user, ready]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}

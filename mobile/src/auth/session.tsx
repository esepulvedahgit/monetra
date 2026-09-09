import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState, type AppStateStatus } from 'react-native';
import { router } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { api, clearReadCache, setReadCacheAccount } from '../api/client';
import type { User } from '../api/types';
import { beginTokenSession, clearSessionTokens, getSessionTokens, isCurrentTokenSession, setSessionTokens } from './sessionTokens';
import type { Tokens } from './tokens';
import { clearSessionData } from './sessionCache';
import { SessionActivityTracker } from './sessionActivity';
import { subscribeSessionExpiry } from './sessionExpiry';

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
  const endingSession = useRef(false);
  const activityTracker = useRef(new SessionActivityTracker());

  const saveUser = useCallback(async (next: User | null) => {
    setUser(next);
    if (next) await AsyncStorage.setItem(userKey, JSON.stringify(next));
    else await AsyncStorage.removeItem(userKey);
  }, []);

  const endSession = useCallback(async (expired = false) => {
    if (endingSession.current) return;
    endingSession.current = true;
    const tokenSession = beginTokenSession();
    setReadCacheAccount(null);
    try {
      await clearSessionData(queryClient, clearReadCache);
    } finally {
      await Promise.allSettled([
        clearSessionTokens(tokenSession),
        activityTracker.current.clear(),
        saveUser(null),
      ]);
      endingSession.current = false;
    }
    if (expired) router.replace({ pathname: '/(auth)/login', params: { reason: 'session_expired' } });
  }, [queryClient, saveUser]);

  useEffect(() => { void (async () => {
    const [tokens, savedUser] = await Promise.all([getSessionTokens(), AsyncStorage.getItem(userKey)]);
    if (tokens && savedUser) {
      if (!await activityTracker.current.returnToForeground(Date.now(), () => true)) {
        await endSession(true);
      } else {
        beginTokenSession();
        const savedAccount = JSON.parse(savedUser) as User;
        setReadCacheAccount(savedAccount.id);
        setUser(savedAccount);
        try {
          const response = await api.get<User>('/me');
          await saveUser(response.data);
        } catch { /* Offline requests retain the last known account. */ }
      }
    }
    setReady(true);
  })(); }, [endSession, saveUser]);

  useEffect(() => subscribeSessionExpiry((tokenSession) => {
    if (isCurrentTokenSession(tokenSession)) void endSession(true);
  }), [endSession]);

  useEffect(() => {
    if (!ready) return;
    let previousState: AppStateStatus = AppState.currentState;
    const subscription = AppState.addEventListener('change', (nextState) => {
      const leftForeground = previousState === 'active' && (nextState === 'inactive' || nextState === 'background');
      const returnedToForeground = (previousState === 'inactive' || previousState === 'background') && nextState === 'active';
      previousState = nextState;
      if (leftForeground) {
        void activityTracker.current.recordInactive(Date.now()).catch(() => undefined);
      } else if (returnedToForeground) {
        void (async () => {
          const sessionIsActive = await activityTracker.current.returnToForeground(Date.now(), () => AppState.currentState === 'active');
          if (sessionIsActive === null) return;
          if (!sessionIsActive) {
            await endSession(true);
            return;
          }
          if (user) {
            try { await api.get<User>('/me'); } catch { /* The interceptor ends invalid sessions. */ }
          }
        })();
      }
    });
    return () => subscription.remove();
  }, [endSession, ready, user]);

  const value = useMemo<SessionContextValue>(() => ({
    user, ready,
    signIn: async (tokens, account) => {
      const tokenSession = beginTokenSession();
      setReadCacheAccount(account.id);
      await clearSessionData(queryClient, clearReadCache);
      await activityTracker.current.clear();
      await setSessionTokens(tokenSession, tokens);
      await saveUser(account);
    },
    signOut: async () => {
      try {
        const tokens = await getSessionTokens();
        if (tokens) await api.post('/logout', undefined, { headers: { Authorization: `Bearer ${tokens.refreshToken}` } });
      } catch { /* local logout still succeeds */ }
      await endSession();
    },
    reloadUser: async () => {
      const response = await api.get<User>('/me');
      if (user && user.id !== response.data.id) await clearSessionData(queryClient, clearReadCache);
      setReadCacheAccount(response.data.id);
      await saveUser(response.data);
    },
  }), [endSession, queryClient, user, ready, saveUser]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}

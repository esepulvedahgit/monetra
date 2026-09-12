import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState, type AppStateStatus } from 'react-native';
import { router } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { api, clearReadCache, setReadCacheAccount, validateQuickAccessStatus } from '../api/client';
import type { User } from '../api/types';
import { beginTokenSession, clearSessionTokens, getSessionTokens, isCurrentTokenSession, setSessionTokens } from './sessionTokens';
import type { Tokens } from './tokens';
import { clearDeviceCredentialVault, enrollDeviceCredentialVault, getDeviceCredentialVaultStatus, lockDeviceCredentialVault, rotateDeviceCredentialVault, unlockDeviceCredentialVault } from './deviceCredentialVault';
import { configureQuickAccessVault, disableQuickAccess, enableQuickAccess, isQuickAccessEnabled, lockQuickAccess, markQuickAccessLocked, unlockQuickAccess } from './tokens';
import { clearSessionData } from './sessionCache';
import { SessionActivityTracker } from './sessionActivity';
import { subscribeSessionExpiry } from './sessionExpiry';
import { initializeQuickAccessLock, lockQuickAccessAfterInactivity, restoreQuickAccessSession, shouldKeepQuickAccessLocked } from './quickAccessLifecycle';
import { shouldDiscardQuickAccessAfterStatusCheck } from './quickAccessStatus';

type SessionContextValue = {
  user: User | null;
  ready: boolean;
  locked: boolean;
  quickAccessSupported: boolean;
  quickAccessEnabled: boolean;
  signIn: (tokens: Tokens, user: User) => Promise<void>;
  signOut: () => Promise<void>;
  reloadUser: () => Promise<void>;
  enableQuickAccess: () => Promise<void>;
  disableQuickAccess: () => Promise<void>;
  unlockQuickAccess: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | undefined>(undefined);
const userKey = 'monetra.mobile.user.v1';

configureQuickAccessVault({
  enroll: enrollDeviceCredentialVault,
  rotate: rotateDeviceCredentialVault,
  lock: lockDeviceCredentialVault,
  clear: clearDeviceCredentialVault,
});

export function SessionProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [locked, setLocked] = useState(false);
  const [quickAccessSupported, setQuickAccessSupported] = useState(false);
  const [quickAccessEnabled, setQuickAccessEnabled] = useState(false);
  const endingSession = useRef(false);
  const unlockingSession = useRef<Promise<void> | null>(null);
  const activityTracker = useRef(new SessionActivityTracker());

  const saveUser = useCallback(async (next: User | null, persist = true) => {
    setUser(next);
    if (next && persist) await AsyncStorage.setItem(userKey, JSON.stringify(next));
    else if (!next || !persist) await AsyncStorage.removeItem(userKey);
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
    setLocked(false);
    setQuickAccessEnabled(false);
    if (expired) router.replace({ pathname: '/(auth)/login', params: { reason: 'session_expired' } });
  }, [queryClient, saveUser]);

  const lockForInactivity = useCallback(async () => {
    const vault = await getDeviceCredentialVaultStatus();
    const tokenSession = beginTokenSession();
    setReadCacheAccount(null);
    const result = await lockQuickAccessAfterInactivity({
      enrolled: vault.enrolled,
      fullSignOut: () => endSession(true),
      clearSessionData: async () => { try { await clearSessionData(queryClient, clearReadCache); } catch { /* lock still takes precedence */ } },
      lockVault: lockQuickAccess,
      clearActivity: () => activityTracker.current.clear(),
      clearUser: () => saveUser(null),
    });
    if (result === 'locked' && isCurrentTokenSession(tokenSession)) {
      setQuickAccessEnabled(true);
      setLocked(true);
      router.replace('/(auth)/unlock');
    }
  }, [endSession, queryClient, saveUser]);

  useEffect(() => { void (async () => {
    const vault = await getDeviceCredentialVaultStatus();
    setQuickAccessSupported(vault.supported);
    if (vault.enrolled && vault.quickAccessStatusToken) {
      try {
        await validateQuickAccessStatus(vault.quickAccessStatusToken);
      } catch (error) {
        if (shouldDiscardQuickAccessAfterStatusCheck(error)) {
          await endSession(true);
          setReady(true);
          return;
        }
      }
    }
    if (await initializeQuickAccessLock({
      enrolled: vault.enrolled,
      markLocked: markQuickAccessLocked,
      clearSessionData: async () => { try { await clearSessionData(queryClient, clearReadCache); } catch { /* locked state still clears other local data */ } },
      clearActivity: () => activityTracker.current.clear(),
      clearUser: () => saveUser(null),
    })) {
      setReadCacheAccount(null);
      setQuickAccessEnabled(true);
      setLocked(true);
      setReady(true);
      return;
    }
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
    } else if (savedUser) {
      // A normal session is memory-only. Do not leave an old account profile
      // behind after Android has terminated the process.
      await saveUser(null);
    }
    setReady(true);
  })(); }, [endSession, queryClient, saveUser]);

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
      // Android's credential screen also causes foreground transitions. While
      // locked, the unlock flow alone owns session restoration and token rotation.
      if (locked || unlockingSession.current) return;
      if (leftForeground) {
        void activityTracker.current.recordInactive(Date.now()).catch(() => undefined);
      } else if (returnedToForeground) {
        void (async () => {
          const sessionIsActive = await activityTracker.current.returnToForeground(Date.now(), () => AppState.currentState === 'active');
          if (unlockingSession.current) return;
          if (sessionIsActive === null) return;
          if (!sessionIsActive) {
            await lockForInactivity();
            return;
          }
          if (user && !locked) {
            try { await api.get<User>('/me'); } catch { /* The interceptor ends invalid sessions. */ }
          }
        })();
      }
    });
    return () => subscription.remove();
  }, [lockForInactivity, locked, ready, user]);

  const value = useMemo<SessionContextValue>(() => ({
    user, ready, locked, quickAccessSupported, quickAccessEnabled,
    signIn: async (tokens, account) => {
      const tokenSession = beginTokenSession();
      setReadCacheAccount(account.id);
      await clearSessionData(queryClient, clearReadCache);
      await activityTracker.current.clear();
      await clearSessionTokens(tokenSession);
      await setSessionTokens(tokenSession, tokens);
      await saveUser(account);
      setLocked(false);
      setQuickAccessEnabled(false);
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
      await saveUser(response.data, !await isQuickAccessEnabled());
    },
    enableQuickAccess: async () => {
      const tokens = await getSessionTokens();
      if (!tokens) throw new Error('Tu sesión ya no está disponible. Ingresa nuevamente.');
      const vault = await getDeviceCredentialVaultStatus();
      if (!vault.supported) throw new Error('El acceso rápido requiere Android 11 o superior y un bloqueo de pantalla configurado.');
      await enableQuickAccess(tokens);
      try {
        await AsyncStorage.removeItem(userKey);
      } catch (error) {
        await endSession(true);
        throw error;
      }
      setQuickAccessEnabled(true);
    },
    disableQuickAccess: async () => {
      await disableQuickAccess();
      if (user) await saveUser(user);
      setQuickAccessEnabled(false);
    },
    unlockQuickAccess: () => {
      if (unlockingSession.current) return unlockingSession.current;
      unlockingSession.current = (async () => {
      try {
        let tokenSession: number | null = null;
        const account = await restoreQuickAccessSession({
          unlockVault: unlockDeviceCredentialVault,
          refresh: async (refreshToken) => {
            const refreshed = await api.post<{ access_token: string; refresh_token: string; quick_access_status_token?: string }>('/refresh', undefined, {
              headers: { Authorization: `Bearer ${refreshToken}` },
            });
            return {
              accessToken: refreshed.data.access_token,
              refreshToken: refreshed.data.refresh_token,
              quickAccessStatusToken: refreshed.data.quick_access_status_token,
            };
          },
          restoreTokens: async (tokens) => {
            tokenSession = beginTokenSession();
            await unlockQuickAccess(tokens);
          },
          loadUser: async () => (await api.get<User>('/me')).data,
          lockSession: lockQuickAccess,
        });
        if (tokenSession === null || !isCurrentTokenSession(tokenSession)) {
          throw Object.assign(new Error('La recuperación fue cancelada porque la sesión cambió.'), { code: 'CANCELLED' });
        }
        setReadCacheAccount(account.id);
        await saveUser(account, false);
        setLocked(false);
      } catch (error) {
        const failure = error as { code?: string; response?: { status?: number } } | null;
        console.warn('Quick access recovery failed', {
          code: failure?.code ?? 'LOCAL_RECOVERY_ERROR',
          status: failure?.response?.status ?? null,
        });
        if (shouldKeepQuickAccessLocked(error)) throw error;
        await clearDeviceCredentialVault();
        const rejected = failure?.response?.status === 401 || failure?.response?.status === 403;
        await endSession(rejected);
        if (!rejected) router.replace({ pathname: '/(auth)/login', params: { reason: 'quick_access_unavailable' } });
        throw error;
      } finally {
        unlockingSession.current = null;
      }
      })();
      return unlockingSession.current;
    },
  }), [endSession, locked, queryClient, quickAccessEnabled, quickAccessSupported, ready, saveUser, user]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}

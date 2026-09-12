import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

// Only native storage and the HTTP transport are substituted. The request
// interceptors, token ownership and quick-access lifecycle run together.
vi.mock('@react-native-async-storage/async-storage', () => ({ default: {
  getItem: async () => null, setItem: async () => undefined,
  removeItem: async () => undefined, getAllKeys: async () => [],
} }));
vi.mock('expo-secure-store', () => ({
  getItemAsync: async () => null, setItemAsync: async () => undefined,
  deleteItemAsync: async () => undefined,
}));

import { api, setReadCacheAccount } from '../src/api/client';
import { beginTokenSession } from '../src/auth/sessionTokens';
import { clearTokens, configureQuickAccessVault, enableQuickAccess, getTokens, lockQuickAccess, unlockQuickAccess } from '../src/auth/tokens';
import { lockQuickAccessAfterInactivity, restoreQuickAccessSession } from '../src/auth/quickAccessLifecycle';

describe('quick access with the API client', () => {
  beforeEach(async () => {
    await clearTokens();
    beginTokenSession();
    setReadCacheAccount(null);
  });

  it('recovers after the local timeout with an expired access token and a valid refresh token', async () => {
    let sealed = '';
    let open = false;
    configureQuickAccessVault({
      enroll: async (token) => { sealed = token; open = true; },
      rotate: async (token) => {
        if (!open) throw new Error('Vault is locked');
        sealed = token;
      },
      lock: async () => { open = false; },
      clear: async () => { sealed = ''; open = false; },
    });
    await enableQuickAccess({ accessToken: 'expired-access', refreshToken: 'valid-30-day-refresh' });
    setReadCacheAccount(4);
    beginTokenSession();
    setReadCacheAccount(null);
    await expect(lockQuickAccessAfterInactivity({
      enrolled: true,
      fullSignOut: async () => { throw new Error('Must not sign out'); },
      clearSessionData: async () => undefined,
      clearActivity: async () => undefined,
      clearUser: async () => undefined,
      lockVault: lockQuickAccess,
    })).resolves.toBe('locked');
    expect(await getTokens()).toBeNull();

    const requests: string[] = [];
    api.defaults.adapter = async (config) => {
      requests.push(config.url!);
      const authorized = config.url === '/refresh'
        ? config.headers.Authorization === 'Bearer valid-30-day-refresh'
        : config.headers.Authorization === 'Bearer renewed-access';
      const response = {
        config, status: authorized ? 200 : 401, statusText: '', headers: new AxiosHeaders(),
        data: config.url === '/refresh'
          ? { access_token: 'renewed-access', refresh_token: 'rotated-refresh' }
          : { id: 4 },
      };
      if (!authorized) throw new AxiosError('Token expired', 'ERR_BAD_REQUEST', config, undefined, response);
      return response;
    };
    const account = await restoreQuickAccessSession({
      unlockVault: async () => { open = true; return sealed; },
      refresh: async (refreshToken) => {
        const { data } = await api.post('/refresh', undefined, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        });
        return { accessToken: data.access_token, refreshToken: data.refresh_token };
      },
      restoreTokens: async (tokens) => { beginTokenSession(); await unlockQuickAccess(tokens); },
      loadUser: async () => (await api.get('/me')).data,
      lockSession: lockQuickAccess,
    });
    expect(account).toEqual({ id: 4 });
    expect(requests).toEqual(['/refresh', '/me']);
    expect(sealed).toBe('rotated-refresh');
    expect(await getTokens()).toEqual({ accessToken: 'renewed-access', refreshToken: 'rotated-refresh' });
  });
});

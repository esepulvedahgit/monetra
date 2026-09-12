import { describe, expect, it, vi } from 'vitest';

import { initializeQuickAccessLock, lockQuickAccessAfterInactivity, restoreQuickAccessSession, shouldKeepQuickAccessLocked } from '../src/auth/quickAccessLifecycle';
import { QuickAccessTokenStore } from '../src/auth/quickAccessTokenStore';

describe('quick access lifecycle', () => {
  it('enters cold-start locked mode only after clearing user and caches', async () => {
    const calls: string[] = [];

    const locked = await initializeQuickAccessLock({
      enrolled: true,
      markLocked: () => calls.push('mark'),
      clearSessionData: async () => { calls.push('cache'); },
      clearActivity: async () => { calls.push('activity'); },
      clearUser: async () => { calls.push('user'); },
    });

    expect(locked).toBe(true);
    expect(calls).toEqual(['mark', 'cache', 'activity', 'user']);
  });

  it('still removes user and activity state when one cold-start cleanup fails', async () => {
    const clearUser = vi.fn(async () => undefined);
    const clearActivity = vi.fn(async () => undefined);

    await expect(initializeQuickAccessLock({
      enrolled: true,
      markLocked: vi.fn(),
      clearSessionData: async () => { throw new Error('cache failure'); },
      clearActivity,
      clearUser,
    })).resolves.toBe(true);

    expect(clearActivity).toHaveBeenCalledOnce();
    expect(clearUser).toHaveBeenCalledOnce();
  });

  it('fully signs out after timeout when no vault is enrolled', async () => {
    const signOut = vi.fn(async () => undefined);
    const lock = vi.fn(async () => undefined);

    await expect(lockQuickAccessAfterInactivity({ enrolled: false, fullSignOut: signOut, clearSessionData: vi.fn(), lockVault: lock, clearActivity: vi.fn(), clearUser: vi.fn() })).resolves.toBe('signedOut');

    expect(signOut).toHaveBeenCalledOnce();
    expect(lock).not.toHaveBeenCalled();
  });

  it('clears UI data before locking an enrolled session after timeout', async () => {
    const calls: string[] = [];

    await expect(lockQuickAccessAfterInactivity({
      enrolled: true,
      fullSignOut: async () => { calls.push('signout'); },
      clearSessionData: async () => { calls.push('cache'); },
      lockVault: async () => { calls.push('vault'); },
      clearActivity: async () => { calls.push('activity'); },
      clearUser: async () => { calls.push('user'); },
    })).resolves.toBe('locked');

    expect(calls).toEqual(['cache', 'vault', 'activity', 'user']);
  });

  it('falls back to full sign-out when the vault cannot lock, while still clearing UI data', async () => {
    const fullSignOut = vi.fn(async () => undefined);
    const clearUser = vi.fn(async () => undefined);
    const clearActivity = vi.fn(async () => undefined);

    await expect(lockQuickAccessAfterInactivity({
      enrolled: true,
      fullSignOut,
      clearSessionData: async () => undefined,
      lockVault: async () => { throw new Error('vault failure'); },
      clearActivity,
      clearUser,
    })).resolves.toBe('signedOut');

    expect(clearActivity).toHaveBeenCalledOnce();
    expect(clearUser).toHaveBeenCalledOnce();
    expect(fullSignOut).toHaveBeenCalledOnce();
  });

  it('restores a locked session by refreshing before requesting the user', async () => {
    const calls: string[] = [];
    const result = await restoreQuickAccessSession({
      unlockVault: async () => { calls.push('unlock'); return 'old-refresh'; },
      refresh: async (refreshToken) => { calls.push(`refresh:${refreshToken}`); return { accessToken: 'access', refreshToken: 'new-refresh' }; },
      restoreTokens: async (tokens) => { calls.push(`tokens:${tokens.refreshToken}`); },
      loadUser: async () => { calls.push('me'); return { id: 4 }; },
      lockSession: async () => { calls.push('lock'); },
    });

    expect(result).toEqual({ id: 4 });
    expect(calls).toEqual(['unlock', 'refresh:old-refresh', 'tokens:new-refresh', 'me']);
  });

  it('keeps cancellation and device-auth failures locked, but not a rejected server refresh', () => {
    expect(shouldKeepQuickAccessLocked({ code: 'CANCELLED' })).toBe(true);
    expect(shouldKeepQuickAccessLocked({ code: 'AUTH_FAILED' })).toBe(true);
    expect(shouldKeepQuickAccessLocked({ response: { status: 401 } })).toBe(false);
  });

  it.each([
    { code: 'ERR_NETWORK' },
    { code: 'ECONNABORTED' },
    { code: 'ETIMEDOUT' },
    { response: { status: 408 } },
    { response: { status: 429 } },
    { response: { status: 503 } },
    new Error('La sesión cambió antes de completar la solicitud.'),
    { code: 'UNLOCK_FAILED' },
    { response: { status: 404 } },
  ])('preserves quick access on a temporary recovery failure: %j', (error) => {
    expect(shouldKeepQuickAccessLocked(error)).toBe(true);
  });

  it.each([
    { response: { status: 401 } },
    { response: { status: 403 } },
    { code: 'ROTATE_FAILED' },
    { code: 'NOT_ENROLLED' },
  ])('requires sign-in when the credential cannot be reused: %j', (error) => {
    expect(shouldKeepQuickAccessLocked(error)).toBe(false);
  });

  it('preserves the original credential when the refresh request cannot connect', async () => {
    let credential = 'valid-refresh';
    let open = false;
    await expect(restoreQuickAccessSession({
      unlockVault: async () => { open = true; return credential; },
      refresh: async () => { throw { code: 'ERR_NETWORK' }; },
      restoreTokens: async (tokens) => { credential = tokens.refreshToken; },
      loadUser: async () => { throw new Error('Must not load a user before refresh'); },
      lockSession: async () => { open = false; },
    })).rejects.toMatchObject({ code: 'ERR_NETWORK' });
    expect(open).toBe(false);
    expect(credential).toBe('valid-refresh');
  });

  it.each([{ code: 'ERR_NETWORK' }, new Error('La sesión cambió antes de completar la solicitud.')])('relocks after a failed profile request and retries with the newly sealed refresh token: %j', async (failure) => {
    let sealedToken: string | null = null;
    let vaultOpen = false;
    const store = new QuickAccessTokenStore({
      get: async () => null, set: async () => undefined, clear: async () => undefined,
    }, {
      enroll: async (token) => { sealedToken = token; vaultOpen = true; },
      rotate: async (token) => {
        if (!vaultOpen) throw new Error('Vault is locked');
        sealedToken = token;
      },
      lock: async () => { vaultOpen = false; },
      clear: async () => { sealedToken = null; vaultOpen = false; },
    });
    await store.enable({ accessToken: 'expired-access', refreshToken: 'refresh-1' });
    await store.lock();
    let expectedRefresh = 'refresh-1';
    let failProfile = true;
    const recover = () => restoreQuickAccessSession({
      unlockVault: async () => { vaultOpen = true; return sealedToken!; },
      refresh: async (token) => {
        if (token !== expectedRefresh) throw { response: { status: 401 } };
        expectedRefresh = token === 'refresh-1' ? 'refresh-2' : 'refresh-3';
        return { accessToken: 'new-access', refreshToken: expectedRefresh };
      },
      restoreTokens: (tokens) => store.unlock(tokens),
      loadUser: async () => {
        if (failProfile) throw failure;
        return { id: 4 };
      },
      lockSession: () => store.lock(),
    });

    await expect(recover()).rejects.toBe(failure);
    expect(await store.get()).toBeNull();
    expect(vaultOpen).toBe(false);
    expect(sealedToken).toBe('refresh-2');
    expect(await store.isQuickAccessEnabled()).toBe(true);

    failProfile = false;
    await expect(recover()).resolves.toEqual({ id: 4 });
    expect(await store.get()).toEqual({ accessToken: 'new-access', refreshToken: 'refresh-3' });
  });
});

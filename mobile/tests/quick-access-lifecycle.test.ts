import { describe, expect, it, vi } from 'vitest';

import { initializeQuickAccessLock, lockQuickAccessAfterInactivity, restoreQuickAccessSession, shouldKeepQuickAccessLocked } from '../src/auth/quickAccessLifecycle';

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
    });

    expect(result).toEqual({ id: 4 });
    expect(calls).toEqual(['unlock', 'refresh:old-refresh', 'tokens:new-refresh', 'me']);
  });

  it('keeps cancellation and device-auth failures locked, but not a rejected server refresh', () => {
    expect(shouldKeepQuickAccessLocked({ code: 'CANCELLED' })).toBe(true);
    expect(shouldKeepQuickAccessLocked({ code: 'AUTH_FAILED' })).toBe(true);
    expect(shouldKeepQuickAccessLocked({ response: { status: 401 } })).toBe(false);
  });
});

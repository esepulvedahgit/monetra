import { expect, it, vi } from 'vitest';

vi.mock('expo-secure-store', () => ({ deleteItemAsync: async () => undefined }));

it('restores the vault after two process restarts with regular tokens only in memory', async () => {
  let sealed = '';
  let open = false;
  const vault = {
    enroll: async (token: string) => { sealed = token; open = true; },
    rotate: async (token: string) => {
      if (!open) throw new Error('Vault is locked');
      sealed = token;
    },
    lock: async () => { open = false; },
    clear: async () => { sealed = ''; open = false; },
  };
  vi.resetModules();
  const initial = await import('../src/auth/tokens');
  initial.configureQuickAccessVault(vault);
  await initial.setTokens({ accessToken: 'access-0', refreshToken: 'refresh-0' });
  await initial.enableQuickAccess((await initial.getTokens())!);

  for (let restart = 1; restart <= 2; restart += 1) {
    open = false;
    vi.resetModules();
    const tokens = await import('../src/auth/tokens');
    const { initializeQuickAccessLock, restoreQuickAccessSession } = await import('../src/auth/quickAccessLifecycle');
    tokens.configureQuickAccessVault(vault);
    await initializeQuickAccessLock({
      enrolled: Boolean(sealed), markLocked: tokens.markQuickAccessLocked,
      clearSessionData: async () => undefined,
      clearActivity: async () => undefined, clearUser: async () => undefined,
    });
    expect(await tokens.getTokens()).toBeNull();
    const account = await restoreQuickAccessSession({
      unlockVault: async () => { open = true; return sealed; },
      refresh: async (refreshToken) => {
        expect(refreshToken).toBe(`refresh-${restart - 1}`);
        return { accessToken: `access-${restart}`, refreshToken: `refresh-${restart}` };
      },
      restoreTokens: tokens.unlockQuickAccess,
      loadUser: async () => {
        expect(await tokens.getTokens()).toEqual({ accessToken: `access-${restart}`, refreshToken: `refresh-${restart}` });
        return { id: 4 };
      },
      lockSession: tokens.lockQuickAccess,
    });
    expect(account).toEqual({ id: 4 });
    expect(sealed).toBe(`refresh-${restart}`);
  }
});

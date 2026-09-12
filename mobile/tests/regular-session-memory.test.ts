import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async () => JSON.stringify({ accessToken: 'legacy-access', refreshToken: 'legacy-refresh' })),
  setItemAsync: vi.fn(async () => undefined),
  deleteItemAsync: vi.fn(async () => undefined),
}));

import * as SecureStore from 'expo-secure-store';
let getTokens: typeof import('../src/auth/tokens').getTokens;
let setTokens: typeof import('../src/auth/tokens').setTokens;

describe('regular mobile session', () => {
  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();
    ({ getTokens, setTokens } = await import('../src/auth/tokens'));
  });

  it('keeps tokens only in memory when quick access is disabled', async () => {
    const tokens = { accessToken: 'access-1', refreshToken: 'refresh-1' };

    await setTokens(tokens);

    expect(await getTokens()).toEqual(tokens);
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
  });

  it('removes legacy persisted credentials instead of restoring them', async () => {
    await getTokens();

    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('monetra.mobile.tokens.v1');
  });

  it('loses the regular session on a process restart', async () => {
    await setTokens({ accessToken: 'access', refreshToken: 'refresh' });
    vi.resetModules();
    const restarted = await import('../src/auth/tokens');
    expect(await restarted.getTokens()).toBeNull();
  });

  it('keeps a disabled quick-access session only until the next process restart', async () => {
    const current = await import('../src/auth/tokens');
    let sealed: string | null = null;
    current.configureQuickAccessVault({
      enroll: async (token) => { sealed = token; },
      rotate: async (token) => { sealed = token; },
      lock: async () => undefined,
      clear: async () => { sealed = null; },
    });
    const tokens = { accessToken: 'access', refreshToken: 'refresh' };
    await current.enableQuickAccess(tokens);
    await current.disableQuickAccess();
    expect(await current.getTokens()).toEqual(tokens);
    expect(sealed).toBeNull();
    vi.resetModules();
    expect(await (await import('../src/auth/tokens')).getTokens()).toBeNull();
  });
});

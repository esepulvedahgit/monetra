import { describe, expect, it, vi } from 'vitest';

import { QuickAccessTokenStore } from '../src/auth/quickAccessTokenStore';

const tokens = { accessToken: 'access-1', refreshToken: 'refresh-1' };

describe('QuickAccessTokenStore', () => {
  it('moves tokens out of regular persistence when quick access is enabled', async () => {
    const regular = { get: vi.fn(async () => tokens), set: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const vault = { enroll: vi.fn(async () => undefined), rotate: vi.fn(async () => undefined), lock: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const store = new QuickAccessTokenStore(regular, vault);

    await store.enable(tokens);

    expect(vault.enroll).toHaveBeenCalledWith('refresh-1');
    expect(regular.clear).toHaveBeenCalledOnce();
    expect(await store.get()).toEqual(tokens);
  });

  it('keeps tokens inaccessible after locking while preserving the credential vault', async () => {
    const regular = { get: vi.fn(async () => null), set: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const vault = { enroll: vi.fn(async () => undefined), rotate: vi.fn(async () => undefined), lock: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const store = new QuickAccessTokenStore(regular, vault);
    await store.enable(tokens);

    await store.lock();

    expect(vault.lock).toHaveBeenCalledOnce();
    expect(vault.clear).not.toHaveBeenCalled();
    expect(await store.get()).toBeNull();
    expect(await store.isQuickAccessEnabled()).toBe(true);
  });

  it('reseals a rotated refresh token in the vault without regular persistence', async () => {
    const regular = { get: vi.fn(async () => null), set: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const vault = { enroll: vi.fn(async () => undefined), rotate: vi.fn(async () => undefined), lock: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const store = new QuickAccessTokenStore(regular, vault);
    await store.enable(tokens);

    await store.set({ accessToken: 'access-2', refreshToken: 'refresh-2' });

    expect(vault.rotate).toHaveBeenCalledWith('refresh-2');
    expect(regular.set).not.toHaveBeenCalled();
    expect(await store.get()).toEqual({ accessToken: 'access-2', refreshToken: 'refresh-2' });
  });

  it('removes both the in-memory session and vault on full sign-out', async () => {
    const regular = { get: vi.fn(async () => null), set: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const vault = { enroll: vi.fn(async () => undefined), rotate: vi.fn(async () => undefined), lock: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const store = new QuickAccessTokenStore(regular, vault);
    await store.enable(tokens);

    await store.clear();

    expect(vault.clear).toHaveBeenCalledOnce();
    expect(await store.get()).toBeNull();
    expect(await store.isQuickAccessEnabled()).toBe(false);
  });

  it('does not enable quick access when regular token removal fails', async () => {
    const regular = { get: vi.fn(async () => tokens), set: vi.fn(async () => undefined), clear: vi.fn(async () => { throw new Error('storage failure'); }) };
    const vault = { enroll: vi.fn(async () => undefined), rotate: vi.fn(async () => undefined), lock: vi.fn(async () => undefined), clear: vi.fn(async () => undefined) };
    const store = new QuickAccessTokenStore(regular, vault);

    await expect(store.enable(tokens)).rejects.toThrow('storage failure');

    expect(vault.clear).toHaveBeenCalledOnce();
    expect(await store.isQuickAccessEnabled()).toBe(false);
  });
});

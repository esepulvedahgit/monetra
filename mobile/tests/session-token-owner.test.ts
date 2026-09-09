import { describe, expect, it, vi } from 'vitest';

import { SessionTokenOwner } from '../src/auth/tokenOwner';

describe('SessionTokenOwner', () => {
  it('serializes a paused A refresh write behind B session ownership', async () => {
    let stored: string | null = null;
    let releaseAWrite!: () => void;
    const aWriteStarted = new Promise<void>((resolve) => { releaseAWrite = resolve; });
    let pauseAWrite!: () => void;
    const waitForAWrite = new Promise<void>((resolve) => { pauseAWrite = resolve; });
    const persistence = {
      get: vi.fn(async () => stored),
      set: vi.fn(async (value: string) => {
        if (value === 'A') {
          pauseAWrite();
          await aWriteStarted;
        }
        stored = value;
      }),
      clear: vi.fn(async () => { stored = null; }),
    };
    const owner = new SessionTokenOwner(persistence);
    const accountA = owner.begin();
    const aRefreshWrite = owner.set(accountA, 'A');
    await waitForAWrite;

    const accountB = owner.begin();
    const bSignInWrite = owner.set(accountB, 'B');
    releaseAWrite();

    await expect(aRefreshWrite).resolves.toBe(false);
    await expect(bSignInWrite).resolves.toBe(true);
    expect(stored).toBe('B');
  });
});

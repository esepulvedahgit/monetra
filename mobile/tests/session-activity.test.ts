import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}));

import AsyncStorage from '@react-native-async-storage/async-storage';

import { clearLastInactiveAt, isSessionWithinInactivityWindow, readLastInactiveAt, SESSION_IDLE_TIMEOUT_MS, SessionActivityTracker, shouldCloseForInactivity, writeLastInactiveAt } from '../src/auth/sessionActivity';

describe('shouldCloseForInactivity', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('closes the session at exactly fifteen minutes away from the app', () => {
    expect(shouldCloseForInactivity(1_000, 1_000 + SESSION_IDLE_TIMEOUT_MS)).toBe(true);
  });

  it('keeps the session eligible for silent refresh before fifteen minutes', () => {
    expect(shouldCloseForInactivity(1_000, 1_000 + SESSION_IDLE_TIMEOUT_MS - 1)).toBe(false);
  });

  it('restores the persisted inactive time after the app process restarts', async () => {
    vi.mocked(AsyncStorage.getItem).mockResolvedValue('1000');

    await expect(readLastInactiveAt()).resolves.toBe(1_000);
  });

  it('persists the instant the app leaves the foreground', async () => {
    await writeLastInactiveAt(1_000);

    expect(AsyncStorage.setItem).toHaveBeenCalledExactlyOnceWith('monetra.mobile.last-inactive-at.v1', '1000');
  });

  it('removes the activity record when the session ends', async () => {
    await clearLastInactiveAt();

    expect(AsyncStorage.removeItem).toHaveBeenCalledExactlyOnceWith('monetra.mobile.last-inactive-at.v1');
  });

  it('clears the background marker after a short foreground return', async () => {
    vi.mocked(AsyncStorage.getItem).mockResolvedValue('1000');

    await expect(isSessionWithinInactivityWindow(1_000 + SESSION_IDLE_TIMEOUT_MS - 1)).resolves.toBe(true);
    expect(AsyncStorage.removeItem).toHaveBeenCalledExactlyOnceWith('monetra.mobile.last-inactive-at.v1');
  });

  it('preserves the marker when the inactivity window has elapsed', async () => {
    vi.mocked(AsyncStorage.getItem).mockResolvedValue('1000');

    await expect(isSessionWithinInactivityWindow(1_000 + SESSION_IDLE_TIMEOUT_MS)).resolves.toBe(false);
    expect(AsyncStorage.removeItem).not.toHaveBeenCalled();
  });

  it('does not clear a newer background marker from a stale foreground callback', async () => {
    let releaseRead!: () => void;
    let notifyReadStarted!: () => void;
    const readStarted = new Promise<void>((resolve) => { notifyReadStarted = resolve; });
    const pausedRead = new Promise<void>((resolve) => { releaseRead = resolve; });
    const writes: number[] = [];
    const clear = vi.fn(async () => undefined);
    const tracker = new SessionActivityTracker({
      read: async () => { notifyReadStarted(); await pausedRead; return 1_000; },
      write: async (timestamp) => { writes.push(timestamp); },
      clear,
    });
    let active = true;

    const resumed = tracker.returnToForeground(1_001, () => active);
    await readStarted;
    active = false;
    const leftAgain = tracker.recordInactive(2_000);
    releaseRead();

    await expect(resumed).resolves.toBeNull();
    await leftAgain;
    expect(clear).not.toHaveBeenCalled();
    expect(writes).toEqual([2_000]);
  });
});

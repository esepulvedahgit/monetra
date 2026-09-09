import AsyncStorage from '@react-native-async-storage/async-storage';

export const SESSION_IDLE_TIMEOUT_MS = 15 * 60 * 1_000;
const lastInactiveAtKey = 'monetra.mobile.last-inactive-at.v1';

export type SessionActivityStore = {
  read: () => Promise<number | null>;
  write: (timestamp: number) => Promise<void>;
  clear: () => Promise<void>;
};

export function shouldCloseForInactivity(lastInactiveAt: number, now: number): boolean {
  return now - lastInactiveAt >= SESSION_IDLE_TIMEOUT_MS;
}

export async function readLastInactiveAt(): Promise<number | null> {
  const raw = await AsyncStorage.getItem(lastInactiveAtKey);
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : null;
}

export function writeLastInactiveAt(timestamp: number): Promise<void> {
  return AsyncStorage.setItem(lastInactiveAtKey, String(timestamp));
}

export function clearLastInactiveAt(): Promise<void> {
  return AsyncStorage.removeItem(lastInactiveAtKey);
}

export async function isSessionWithinInactivityWindow(now: number): Promise<boolean> {
  const lastInactiveAt = await readLastInactiveAt();
  if (lastInactiveAt && shouldCloseForInactivity(lastInactiveAt, now)) return false;
  await clearLastInactiveAt();
  return true;
}

const defaultStore: SessionActivityStore = {
  read: readLastInactiveAt,
  write: writeLastInactiveAt,
  clear: clearLastInactiveAt,
};

export class SessionActivityTracker {
  private generation = 0;
  private queue: Promise<void> = Promise.resolve();

  constructor(private readonly store: SessionActivityStore = defaultStore) {}

  recordInactive(timestamp: number): Promise<void> {
    this.generation += 1;
    return this.enqueue(() => this.store.write(timestamp));
  }

  clear(): Promise<void> {
    this.generation += 1;
    return this.enqueue(() => this.store.clear());
  }

  returnToForeground(now: number, isActive: () => boolean): Promise<boolean | null> {
    const generation = this.generation;
    return this.enqueue(async () => {
      if (!isActive() || generation !== this.generation) return null;
      const lastInactiveAt = await this.store.read();
      if (!isActive() || generation !== this.generation) return null;
      if (lastInactiveAt && shouldCloseForInactivity(lastInactiveAt, now)) return false;
      await this.store.clear();
      return isActive() && generation === this.generation ? true : null;
    });
  }

  private enqueue<T>(task: () => Promise<T>): Promise<T> {
    const result = this.queue.then(task, task);
    this.queue = result.then(() => undefined, () => undefined);
    return result;
  }
}

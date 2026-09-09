import type { Tokens } from './tokens';

type Cleanup = {
  clearSessionData: () => Promise<void>;
  clearActivity: () => Promise<void>;
  clearUser: () => Promise<void>;
};

export async function initializeQuickAccessLock({ enrolled, markLocked, ...cleanup }: { enrolled: boolean; markLocked: () => void } & Cleanup): Promise<boolean> {
  if (!enrolled) return false;
  markLocked();
  await Promise.allSettled([cleanup.clearSessionData(), cleanup.clearActivity(), cleanup.clearUser()]);
  return true;
}

export async function lockQuickAccessAfterInactivity({ enrolled, fullSignOut, lockVault, ...cleanup }: { enrolled: boolean; fullSignOut: () => Promise<void>; lockVault: () => Promise<void> } & Cleanup): Promise<'locked' | 'signedOut'> {
  if (!enrolled) {
    await fullSignOut();
    return 'signedOut';
  }
  const results = await Promise.allSettled([cleanup.clearSessionData(), lockVault(), cleanup.clearActivity(), cleanup.clearUser()]);
  if (results[1].status === 'rejected') {
    await fullSignOut();
    return 'signedOut';
  }
  return 'locked';
}

export async function restoreQuickAccessSession<User>({ unlockVault, refresh, restoreTokens, loadUser }: {
  unlockVault: () => Promise<string>;
  refresh: (refreshToken: string) => Promise<Tokens>;
  restoreTokens: (tokens: Tokens) => Promise<void>;
  loadUser: () => Promise<User>;
}): Promise<User> {
  const refreshToken = await unlockVault();
  const tokens = await refresh(refreshToken);
  await restoreTokens(tokens);
  return loadUser();
}

export function shouldKeepQuickAccessLocked(error: unknown): boolean {
  const code = (error as { code?: string }).code;
  return code === 'CANCELLED' || code === 'AUTH_FAILED';
}

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

export async function restoreQuickAccessSession<User>({ unlockVault, refresh, restoreTokens, loadUser, lockSession }: {
  unlockVault: () => Promise<string>;
  refresh: (refreshToken: string) => Promise<Tokens>;
  restoreTokens: (tokens: Tokens) => Promise<void>;
  loadUser: () => Promise<User>;
  lockSession: () => Promise<void>;
}): Promise<User> {
  try {
    const refreshToken = await unlockVault();
    const tokens = await refresh(refreshToken);
    await restoreTokens(tokens);
    return await loadUser();
  } catch (error) {
    // A temporary failure is not revocation. Keep the sealed credential (which
    // may already have rotated), but remove unlocked keys/tokens before retrying.
    if (shouldKeepQuickAccessLocked(error)) await lockSession();
    throw error;
  }
}

export function shouldKeepQuickAccessLocked(error: unknown): boolean {
  const failure = error as { code?: string; response?: { status?: number }; message?: string } | null;
  const status = failure?.response?.status;
  if (status !== undefined) return status !== 401 && status !== 403;
  // Unknown local failures do not establish that the server session expired.
  // A failed rotation is different: its one-time replacement could not be sealed.
  return !['ROTATE_FAILED', 'NOT_ENROLLED'].includes(failure?.code ?? '');
}

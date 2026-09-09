import { describe, expect, it } from 'vitest';

import { shouldEndSessionAfterRefreshFailure } from '../src/auth/refreshFailure';

describe('shouldEndSessionAfterRefreshFailure', () => {
  it('ends the session when the refresh credential is rejected', () => {
    expect(shouldEndSessionAfterRefreshFailure({ response: { status: 401 } })).toBe(true);
  });

  it('ends the session when the account is no longer allowed to refresh', () => {
    expect(shouldEndSessionAfterRefreshFailure({ response: { status: 403 } })).toBe(true);
  });

  it('keeps the session on a network failure while refreshing', () => {
    expect(shouldEndSessionAfterRefreshFailure({ code: 'ERR_NETWORK' })).toBe(false);
  });
});

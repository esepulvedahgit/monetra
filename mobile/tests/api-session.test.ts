import { describe, expect, it } from 'vitest';

import { ApiSession } from '../src/api/requestSession';

describe('ApiSession', () => {
  it('rejects account A refresh and retry after account B begins a session', () => {
    const sessions = new ApiSession();
    const accountA = sessions.begin(1);
    const requestA = sessions.capture(accountA);
    sessions.begin(2);

    expect(sessions.isCurrent(accountA)).toBe(false);
    expect(sessions.canRetry(requestA)).toBe(false);
  });
});

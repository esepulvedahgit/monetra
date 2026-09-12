import { describe, expect, it } from 'vitest';

import { shouldDiscardQuickAccessAfterStatusCheck } from '../src/auth/quickAccessStatus';

describe('quick access status validation', () => {
  it('discards the local quick-access vault when the server rejects its status credential', () => {
    expect(shouldDiscardQuickAccessAfterStatusCheck({ response: { status: 401 } })).toBe(true);
    expect(shouldDiscardQuickAccessAfterStatusCheck({ response: { status: 403 } })).toBe(true);
  });

  it('keeps the vault locked when status cannot be checked due to connectivity', () => {
    expect(shouldDiscardQuickAccessAfterStatusCheck({ code: 'ERR_NETWORK' })).toBe(false);
    expect(shouldDiscardQuickAccessAfterStatusCheck({ code: 'ECONNABORTED' })).toBe(false);
  });
});

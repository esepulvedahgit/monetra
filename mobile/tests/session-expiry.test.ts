import { describe, expect, it, vi } from 'vitest';

import { notifySessionExpired, subscribeSessionExpiry } from '../src/auth/sessionExpiry';

describe('session expiry notification', () => {
  it('delivers the failed token session to the current session owner', () => {
    const onExpired = vi.fn();
    const unsubscribe = subscribeSessionExpiry(onExpired);

    notifySessionExpired(7);

    expect(onExpired).toHaveBeenCalledExactlyOnceWith(7);
    unsubscribe();
  });

  it('does not notify an owner after it unsubscribes', () => {
    const onExpired = vi.fn();
    const unsubscribe = subscribeSessionExpiry(onExpired);
    unsubscribe();

    notifySessionExpired(7);

    expect(onExpired).not.toHaveBeenCalled();
  });
});

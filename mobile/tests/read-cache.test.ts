import { describe, expect, it } from 'vitest';

import { readCacheKey } from '../src/api/readCache';

describe('readCacheKey', () => {
  it('isolates the same request for different authenticated accounts', () => {
    const first = readCacheKey('/transactions', { page: 1 }, 17);
    const second = readCacheKey('/transactions', { page: 1 }, 42);

    expect(first).not.toBe(second);
    expect(first).toContain(':17:');
    expect(second).toContain(':42:');
  });
});

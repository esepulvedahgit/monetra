import { describe, expect, it, vi } from 'vitest';

import { clearSessionData } from '../src/auth/sessionCache';

describe('clearSessionData', () => {
  it('cancels and clears React Query before removing persistent read data', async () => {
    const events: string[] = [];
    const queryClient = {
      cancelQueries: vi.fn(async () => { events.push('cancel'); }),
      clear: vi.fn(() => { events.push('clear'); }),
    };

    await clearSessionData(queryClient, async () => { events.push('persistent'); });

    expect(events).toEqual(['cancel', 'clear', 'persistent']);
  });
});

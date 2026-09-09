import { describe, expect, it } from 'vitest';

import { colors, radii, spacing } from '../src/theme/tokens';

describe('design tokens', () => {
  it('exposes the approved Monetra primary color', () => {
    expect(colors.accent).toBe('#0075de');
  });

  it('keeps the four-point spacing scale and card radius from the reference design', () => {
    expect(spacing.md).toBe(16);
    expect(radii.lg).toBe(12);
  });
});

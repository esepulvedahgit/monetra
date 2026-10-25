import { describe, expect, it } from 'vitest';

import { colors, darkColors, radii, spacing } from '../src/theme/tokens';
import { isThemePreference, resolveColorScheme } from '../src/theme/preference';

describe('design tokens', () => {
  it('exposes the approved Monetra primary color', () => {
    expect(colors.accent).toBe('#0075de');
  });

  it('keeps the four-point spacing scale and card radius from the reference design', () => {
    expect(spacing.md).toBe(16);
    expect(radii.lg).toBe(12);
  });
});

describe('dark theme', () => {
  it('defines every light color so screens never fall back to light values', () => {
    expect(Object.keys(darkColors).sort()).toEqual(Object.keys(colors).sort());
  });

  it("follows the web app's default dark palette", () => {
    expect(darkColors.background).toBe('#0A1428');
    expect(darkColors.card).toBe('#0D1B35');
    expect(darkColors.accent).toBe('#00C896');
    expect(darkColors.onAccent).toBe('#070E1E');
  });

  it('resolves the stored preference against the system scheme', () => {
    expect(resolveColorScheme('system', 'dark')).toBe('dark');
    expect(resolveColorScheme('system', null)).toBe('light');
    expect(resolveColorScheme('light', 'dark')).toBe('light');
    expect(resolveColorScheme('dark', 'light')).toBe('dark');
    expect(isThemePreference('dark')).toBe(true);
    expect(isThemePreference('sepia')).toBe(false);
  });
});

import { colors, radii, shadows, spacing } from './tokens';

export type ThemeColors = { readonly [K in keyof typeof colors]: string };

export type Theme = {
  scheme: 'light';
  colors: ThemeColors;
  spacing: typeof spacing;
  radii: typeof radii;
  shadows: typeof shadows;
};

const lightTheme: Theme = { scheme: 'light', colors, spacing, radii, shadows };

/**
 * Screens read colors through this hook instead of importing tokens directly so a
 * dark palette can be added later without touching them. app.json pins
 * userInterfaceStyle to "light", so only the light theme exists for now.
 */
export const useTheme = (): Theme => lightTheme;

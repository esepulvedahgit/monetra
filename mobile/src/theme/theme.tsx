import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { Appearance, useColorScheme } from 'react-native';

import { colors, darkColors, radii, shadows, spacing, type ThemeColors } from './tokens';
import { isThemePreference, resolveColorScheme, type ColorScheme, type ThemePreference } from './preference';

export type { ThemeColors } from './tokens';
export type { ColorScheme, ThemePreference } from './preference';

export type Theme = {
  scheme: ColorScheme;
  colors: ThemeColors;
  spacing: typeof spacing;
  radii: typeof radii;
  shadows: typeof shadows;
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
};

const preferenceKey = 'monetra.mobile.theme.v1';
const palettes: Record<ColorScheme, ThemeColors> = { light: colors, dark: darkColors };

const lightTheme: Theme = { scheme: 'light', colors, spacing, radii, shadows, preference: 'light', setPreference: () => undefined };
const ThemeContext = createContext<Theme>(lightTheme);

export function ThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreferenceState] = useState<ThemePreference>('system');
  const system = useColorScheme();

  useEffect(() => { void AsyncStorage.getItem(preferenceKey).then((stored) => {
    if (isThemePreference(stored)) setPreferenceState(stored);
  }).catch(() => undefined); }, []);

  // Native surfaces (alerts, keyboard, date pickers) follow the same choice.
  useEffect(() => { Appearance.setColorScheme(preference === 'system' ? 'unspecified' : preference); }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    void AsyncStorage.setItem(preferenceKey, next).catch(() => undefined);
  }, []);

  const value = useMemo<Theme>(() => {
    const scheme = resolveColorScheme(preference, system);
    return { scheme, colors: palettes[scheme], spacing, radii, shadows, preference, setPreference };
  }, [preference, setPreference, system]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * Screens read colors through this hook instead of importing tokens directly, so
 * the light and dark palettes switch without restarting the app.
 */
export const useTheme = (): Theme => useContext(ThemeContext);

/** Builds a StyleSheet once per palette; `factory` must be defined at module level. */
export function useThemedStyles<T>(factory: (colors: ThemeColors) => T): T {
  const { colors: palette } = useTheme();
  return useMemo(() => factory(palette), [factory, palette]);
}

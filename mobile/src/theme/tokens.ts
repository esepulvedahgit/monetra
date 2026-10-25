export const colors = {
  background: '#ffffff',
  surface: '#f6f5f4',
  card: '#ffffff',
  surfaceBlue: '#f2f9ff',
  text: '#31302e',
  textStrong: '#000000',
  muted: '#615d59',
  meta: '#a39e98',
  border: 'rgba(0,0,0,0.1)',
  borderSoft: 'rgba(0,0,0,0.06)',
  accent: '#0075de',
  accentPressed: '#005bab',
  success: '#1aae39',
  warning: '#dd5b00',
  danger: '#dc2626',
  onAccent: '#ffffff',
  successSoft: '#e8faf0',
  warningSoft: '#fff1ed',
  dangerSoft: '#fff0f0',
  track: '#e2dfdc',
  chartTrack: '#eeeae7',
  balanceSurface: '#31302e',
  onBalance: '#ffffff',
  onBalanceMuted: 'rgba(255,255,255,.72)',
  balancePositive: '#d9f6df',
  scrim: 'rgba(49,48,46,.35)',
} as const;

export type ThemeColors = { readonly [K in keyof typeof colors]: string };

/** Mirrors the web app's default "dark" theme (site_finanzas/app/static/css/themes.css). */
export const darkColors: ThemeColors = {
  background: '#0A1428',
  surface: '#102040',
  card: '#0D1B35',
  surfaceBlue: 'rgba(0,200,150,0.12)',
  text: '#FFFFFF',
  textStrong: '#FFFFFF',
  muted: '#B0BEC5',
  meta: '#78909C',
  border: 'rgba(255,255,255,0.08)',
  borderSoft: 'rgba(255,255,255,0.05)',
  accent: '#00C896',
  accentPressed: '#00A67E',
  success: '#00C896',
  warning: '#F2C94C',
  danger: '#EF4444',
  onAccent: '#070E1E',
  successSoft: 'rgba(0,200,150,0.14)',
  warningSoft: 'rgba(242,201,76,0.14)',
  dangerSoft: 'rgba(239,68,68,0.14)',
  track: 'rgba(255,255,255,0.10)',
  chartTrack: 'rgba(255,255,255,0.08)',
  balanceSurface: '#0D2535',
  onBalance: '#FFFFFF',
  onBalanceMuted: 'rgba(255,255,255,.72)',
  balancePositive: '#1FE0B0',
  scrim: 'rgba(0,0,0,.6)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 20,
  xl: 24,
} as const;

export const radii = {
  sm: 4,
  md: 8,
  lg: 12,
  pill: 9999,
} as const;

export const shadows = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
    elevation: 3,
  },
} as const;

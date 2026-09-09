export const colors = {
  background: '#ffffff',
  surface: '#f6f5f4',
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
} as const;

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

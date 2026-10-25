import { ReactNode } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { mobileContentInsets } from './layout/mobileLayout';
import { radii, shadows, spacing } from './theme/tokens';
import { useTheme } from './theme/theme';

export function Screen({ children, refreshing, onRefresh }: { children: ReactNode; refreshing?: boolean; onRefresh?: () => void }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  return <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={[{ gap: spacing.md }, mobileContentInsets(insets)]} keyboardDismissMode="on-drag" refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.accent} colors={[colors.accent]} progressBackgroundColor={colors.surface} /> : undefined}>{children}</ScrollView>;
}
export function Card({ children }: { children: ReactNode }) { const { colors, scheme } = useTheme(); return <View style={{ backgroundColor: colors.surface, padding: spacing.md, borderRadius: radii.lg, ...(scheme === 'dark' ? { borderWidth: 1, borderColor: colors.border } : shadows.card) }}>{children}</View>; }
export function Title({ children }: { children: ReactNode }) { const { colors } = useTheme(); return <Text style={{ color: colors.textStrong, fontSize: 25, fontWeight: '800' }}>{children}</Text>; }
export function Loading() { const { colors } = useTheme(); return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><ActivityIndicator color={colors.accent} /></View>; }
export function Money({ value, symbol = '$', inverse = false }: { value: number; symbol?: string; inverse?: boolean }) { const { colors } = useTheme(); return <Text style={{ color: inverse ? colors.onBalance : colors.textStrong, fontWeight: '800', fontSize: 30 }}>{symbol}{value.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</Text>; }

import { ReactNode } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { mobileContentInsets } from './layout/mobileLayout';
import { colors, radii, shadows, spacing } from './theme/tokens';

export function Screen({ children, refreshing, onRefresh }: { children: ReactNode; refreshing?: boolean; onRefresh?: () => void }) {
  const insets = useSafeAreaInsets();
  return <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={[{ gap: spacing.md }, mobileContentInsets(insets)]} keyboardDismissMode="on-drag" refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.accent} /> : undefined}>{children}</ScrollView>;
}
export function Card({ children }: { children: ReactNode }) { return <View style={{ backgroundColor: colors.surface, padding: spacing.md, borderRadius: radii.lg, ...shadows.card }}>{children}</View>; }
export function Title({ children }: { children: ReactNode }) { return <Text style={{ color: colors.textStrong, fontSize: 25, fontWeight: '800' }}>{children}</Text>; }
export function Loading() { return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><ActivityIndicator color={colors.accent} /></View>; }
export function Money({ value, symbol = '$', inverse = false }: { value: number; symbol?: string; inverse?: boolean }) { return <Text style={{ color: inverse ? colors.onAccent : colors.textStrong, fontWeight: '800', fontSize: 30 }}>{symbol}{value.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</Text>; }

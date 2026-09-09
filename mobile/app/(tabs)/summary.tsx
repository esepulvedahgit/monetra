import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { api } from '../../src/api/client';
import type { Summary } from '../../src/api/types';
import { Loading, Screen } from '../../src/ui';
import { colors, radii, spacing } from '../../src/theme/tokens';
import { useSession } from '../../src/auth/session';
import { AppHeader, BalanceCard, BudgetCard, DonutChart, ErrorState, MetricCard, PeriodSwitcher, SectionHeader } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';
import { shiftMonth, transactionsRouteParams, type Period } from '../../src/finance/presentation';

export default function SummaryScreen() {
  const { user } = useSession();
  const now = new Date(); const [period, setPeriod] = useState<Period>({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const query = useQuery({ queryKey: ['summary', period.year, period.month], queryFn: async () => (await api.get<Summary>(`/dashboard/summary?year=${period.year}&month=${period.month}`)).data });
  const openTransactions = () => router.push({ pathname: '/(tabs)/transactions', params: transactionsRouteParams(period) });
  if (query.isLoading) return <Loading />;
  if (query.isError || !query.data) return <Screen refreshing={query.isFetching} onRefresh={() => void query.refetch()}><AppHeader /><ErrorState title="No pudimos cargar tu resumen" onRetry={() => void query.refetch()} /></Screen>;
  const data = query.data; const symbol = user?.currency_symbol ?? '$';
  return <Screen refreshing={query.isFetching} onRefresh={() => void query.refetch()}><AppHeader action="plus" onAction={() => router.push({ pathname: '/(tabs)/transactions', params: { ...transactionsRouteParams(period), create: '1' } })} /><Text style={styles.eyebrow}>Panorama mensual</Text><Text style={styles.heading}>Tus finanzas, claras.</Text><Text style={styles.copy}>Revisa tu avance y registra cada movimiento.</Text><PeriodSwitcher period={period} onChange={(direction) => setPeriod((current) => shiftMonth(current, direction))} /><BalanceCard balance={data.balance} income={data.total_income} expense={data.total_expense} symbol={symbol} />
    <SectionHeader title="Este mes" actionLabel="Ver movimientos" onAction={openTransactions} /><View style={styles.metricGrid}><MetricCard icon="income" label="Ingresos totales" value={data.total_income} caption="Ingresos registrados" tone="income" symbol={symbol} /><MetricCard icon="expense" label="Gastos totales" value={data.total_expense} caption="Gastos registrados" tone="expense" symbol={symbol} /></View>
    <SectionHeader title="Presupuesto" /><BudgetCard limit={data.budget.limit} spent={data.budget.spent} remaining={data.budget.remaining} usedPct={data.budget.used_pct} daysRemaining={data.budget.days_remaining} symbol={symbol} />
    <SectionHeader title="Gastos por categoría" actionLabel="Ver movimientos" onAction={openTransactions} />{data.expense_categories.length ? <DonutChart categories={data.expense_categories} /> : <View style={styles.noChart}><Text style={styles.noChartText}>Aún no hay gastos en este período.</Text></View>}
    <SectionHeader title="Últimos movimientos" actionLabel="Ver todos" onAction={openTransactions} />{data.recent_transactions.length ? data.recent_transactions.map((item) => <Pressable key={item.id} onPress={openTransactions} style={styles.recentRow}><View style={[styles.recentIcon, { backgroundColor: item.type === 'income' ? '#e8faf0' : '#fff1ed' }]}><Icon name={item.type === 'income' ? 'income' : 'expense'} color={item.type === 'income' ? colors.success : colors.warning} size={18} /></View><View style={{ flex: 1 }}><Text style={styles.recentDescription}>{item.description || item.category_name || 'Movimiento'}</Text><Text style={styles.recentDate}>{item.category_name ? `${item.category_name} · ` : ''}{item.date}</Text></View><Text style={[styles.recentAmount, { color: item.type === 'income' ? colors.success : colors.text }]}>{item.type === 'income' ? '+' : '−'}{symbol}{item.amount.toLocaleString('es-CL')}</Text></Pressable>) : <View style={styles.noChart}><Text style={styles.noChartText}>Registra tu primer movimiento para ver actividad aquí.</Text></View>}</Screen>;
}

const styles = StyleSheet.create({ eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase', marginTop: spacing.sm }, heading: { color: colors.text, fontSize: 29, fontWeight: '800', letterSpacing: -1.1, marginTop: 5 }, copy: { color: colors.muted, fontSize: 14, lineHeight: 21, marginTop: 7 }, metricGrid: { flexDirection: 'row', gap: 10 }, noChart: { padding: spacing.lg, borderRadius: radii.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, noChartText: { color: colors.muted, textAlign: 'center' }, recentRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9 }, recentIcon: { width: 34, height: 34, borderRadius: 9, alignItems: 'center', justifyContent: 'center' }, recentDescription: { color: colors.text, fontSize: 14, fontWeight: '700' }, recentDate: { color: colors.muted, marginTop: 2, fontSize: 12 }, recentAmount: { fontSize: 14, fontWeight: '800' } });

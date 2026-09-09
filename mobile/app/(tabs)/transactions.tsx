import { useEffect, useMemo, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { api } from '../../src/api/client';
import type { Category, Transaction } from '../../src/api/types';
import { Loading, Screen } from '../../src/ui';
import { colors, radii, shadows, spacing } from '../../src/theme/tokens';
import { useSession } from '../../src/auth/session';
import { AppHeader, EmptyState, ErrorState, PrimaryButton } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';
import { confirmDeleteTransaction, TransactionEditor } from '../../src/features/transactions/TransactionEditor';
import { TransactionFilterSheet } from '../../src/features/transactions/TransactionFilterSheet';
import { useTransactionMutations } from '../../src/features/transactions/useTransactionMutations';
import { flattenTransactionPages, type TransactionPage } from '../../src/features/transactions/pagination';
import { compactFilterLabel, groupTransactionsByDate } from '../../src/features/transactions/presentation';
import { periodFromRouteParams, transactionPeriodParams } from '../../src/finance/presentation';

const dateLabel = (date: string) => new Intl.DateTimeFormat('es-CL', { day: 'numeric', month: 'long' }).format(new Date(`${date}T12:00:00`));
const typeLabel = (type: 'all' | Transaction['type']) => type === 'all' ? 'Todos' : type === 'expense' ? 'Gastos' : 'Ingresos';

export default function TransactionsScreen() {
  const { create, year, month } = useLocalSearchParams<{ create?: string; year?: string; month?: string }>();
  const period = periodFromRouteParams({ year, month });
  const { user } = useSession();
  const [type, setType] = useState<'all' | Transaction['type']>('all');
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const mutations = useTransactionMutations();
  const query = useInfiniteQuery({ queryKey: ['transactions', period.year, period.month], initialPageParam: 1, queryFn: async ({ pageParam }) => (await api.get<TransactionPage>('/transactions', { params: { page: pageParam, per_page: 100, ...transactionPeriodParams(period) } })).data, getNextPageParam: (lastPage, pages) => lastPage.has_next ? pages.length + 1 : undefined });
  const categories = useQuery({ queryKey: ['categories'], queryFn: async () => (await api.get<Category[]>('/categories')).data });

  useEffect(() => {
    if (create === '1') {
      setEditing(null);
      setEditorOpen(true);
      router.setParams({ create: undefined });
    }
  }, [create]);

  const filtered = useMemo(() => flattenTransactionPages(query.data?.pages).filter((item) => (type === 'all' || item.type === type) && (categoryId === null || item.category_id === categoryId)), [query.data, type, categoryId]);
  const grouped = useMemo(() => groupTransactionsByDate(filtered), [filtered]);
  const selectedCategory = (categories.data ?? []).find((category) => category.id === categoryId) ?? null;
  const selectedCategoryLabel = compactFilterLabel(selectedCategory);
  const openCreate = () => { setEditing(null); setEditorOpen(true); };
  const remove = (id: number) => confirmDeleteTransaction(() => void mutations.remove.mutateAsync(id).catch((error) => Alert.alert('No pudimos eliminarlo', error instanceof Error ? error.message : 'Inténtalo nuevamente.')));
  const selectType = (next: 'all' | Transaction['type']) => { setType(next); setCategoryId(null); };

  if (query.isLoading) return <Loading />;

  return (
    <Screen refreshing={query.isFetching || categories.isFetching} onRefresh={() => { void query.refetch(); void categories.refetch(); }}>
      {query.isError ? (
        <>
          <AppHeader />
          <ErrorState title="No pudimos cargar tus movimientos" onRetry={() => void query.refetch()} />
        </>
      ) : (
        <>
          <AppHeader />
          <View style={styles.head}>
            <View style={styles.headCopy}>
              <Text style={styles.eyebrow}>Registro financiero</Text>
              <Text style={styles.title}>Movimientos</Text>
              <Text style={styles.copy}>Consulta y organiza tus ingresos y gastos.</Text>
            </View>
            <Pressable accessibilityLabel="Agregar movimiento" onPress={openCreate} style={({ pressed }) => [styles.add, pressed && styles.pressed]}>
              <Icon name="plus" color={colors.onAccent} />
            </Pressable>
          </View>

          <View style={styles.filterBar}>
            <View accessibilityRole="radiogroup" style={styles.typeFilters}>
              {(['all', 'expense', 'income'] as const).map((value) => (
                <Pressable key={value} accessibilityLabel={typeLabel(value)} accessibilityRole="radio" accessibilityState={{ selected: type === value }} onPress={() => selectType(value)} style={({ pressed }) => [styles.filter, type === value && styles.filterActive, pressed && styles.pressed]}>
                  <Text style={[styles.filterText, type === value && styles.filterTextActive]}>{typeLabel(value)}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable accessibilityLabel="Filtrar por categoría" accessibilityHint="Abre las categorías disponibles" accessibilityState={{ selected: categoryId !== null }} onPress={() => setFilterOpen(true)} style={({ pressed }) => [styles.filterButton, categoryId !== null && styles.filterButtonActive, pressed && styles.pressed]}>
              <Icon name="filter" color={categoryId !== null ? colors.accent : colors.text} size={19} />
              {categoryId !== null ? <View style={styles.filterBadge} /> : null}
            </Pressable>
          </View>

          {selectedCategoryLabel && selectedCategory ? (
            <View style={styles.activeFilter}>
              <View style={[styles.dot, { backgroundColor: selectedCategory.color }]} />
              <Text style={styles.activeFilterText}>{selectedCategoryLabel}</Text>
              <Pressable accessibilityLabel="Quitar filtro de categoría" hitSlop={8} onPress={() => setCategoryId(null)}>
                <Icon name="close" color={colors.muted} size={16} />
              </Pressable>
            </View>
          ) : null}

          {categories.isError ? <ErrorState title="No pudimos cargar las categorías" onRetry={() => void categories.refetch()} /> : null}
          <Text style={styles.count}>{filtered.length} movimiento{filtered.length === 1 ? '' : 's'} · {new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(new Date(period.year, period.month - 1, 1))}</Text>

          {grouped.length ? grouped.map((group) => (
            <View key={group.date} style={styles.dayGroup}>
              <Text style={styles.day}>{dateLabel(group.date)}</Text>
              {group.transactions.map((item) => (
                <View key={item.id} style={styles.row}>
                  <View style={[styles.rowIcon, { backgroundColor: item.type === 'income' ? '#e8faf0' : '#fff1ed' }]}>
                    <Icon name={item.type === 'income' ? 'income' : 'expense'} color={item.type === 'income' ? colors.success : colors.warning} />
                  </View>
                  <View style={styles.rowCopy}>
                    <Text numberOfLines={1} style={styles.description}>{item.description || item.category_name || 'Sin descripción'}</Text>
                    <Text numberOfLines={1} style={styles.meta}>{item.category_name ?? 'Sin categoría'}</Text>
                  </View>
                  <View style={styles.rowEnd}>
                    <Text style={[styles.amount, { color: item.type === 'income' ? colors.success : colors.text }]}>{item.type === 'income' ? '+' : '−'}{user?.currency_symbol ?? '$'}{item.amount.toLocaleString('es-CL')}</Text>
                    <View style={styles.actions}>
                      <Pressable accessibilityLabel="Editar movimiento" hitSlop={8} onPress={() => { setEditing(item); setEditorOpen(true); }}><Icon name="edit" size={18} color={colors.muted} /></Pressable>
                      <Pressable accessibilityLabel="Eliminar movimiento" hitSlop={8} onPress={() => remove(item.id)}><Icon name="trash" size={18} color={colors.danger} /></Pressable>
                    </View>
                  </View>
                </View>
              ))}
            </View>
          )) : <EmptyState title="Sin movimientos" copy="Usa el botón + junto al título para registrar tu primer movimiento." />}

          {query.hasNextPage ? <PrimaryButton onPress={() => void query.fetchNextPage()} loading={query.isFetchingNextPage}>Cargar más movimientos</PrimaryButton> : null}
        </>
      )}
      <TransactionFilterSheet visible={filterOpen} categories={categories.data ?? []} type={type} selectedCategoryId={categoryId} onSelect={setCategoryId} onClose={() => setFilterOpen(false)} />
      <TransactionEditor visible={editorOpen} transaction={editing} categories={categories.data ?? []} onClose={() => setEditorOpen(false)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  headCopy: { flex: 1, minWidth: 0 },
  eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' },
  title: { color: colors.text, fontSize: 27, fontWeight: '800', marginTop: 4 },
  copy: { color: colors.muted, marginTop: 6, lineHeight: 20 },
  add: { flexShrink: 0, width: 48, height: 48, borderRadius: radii.md, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: .82, transform: [{ scale: .97 }] },
  filterBar: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  typeFilters: { flex: 1, flexDirection: 'row', padding: 3, backgroundColor: colors.surface, borderRadius: radii.md },
  filter: { flex: 1, minHeight: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 6 },
  filterActive: { backgroundColor: colors.background, ...shadows.card },
  filterText: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  filterTextActive: { color: colors.accent },
  filterButton: { width: 44, height: 44, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, alignItems: 'center', justifyContent: 'center' },
  filterButtonActive: { borderColor: colors.accent, backgroundColor: colors.surfaceBlue },
  filterBadge: { position: 'absolute', top: 8, right: 8, width: 7, height: 7, borderRadius: radii.pill, backgroundColor: colors.accent, borderWidth: 1.5, borderColor: colors.background },
  activeFilter: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', gap: 7, paddingVertical: 7, paddingHorizontal: 10, backgroundColor: colors.surfaceBlue, borderRadius: radii.pill },
  dot: { width: 8, height: 8, borderRadius: radii.pill },
  activeFilterText: { color: colors.accent, fontSize: 12, fontWeight: '800' },
  count: { color: colors.muted, fontSize: 13, textTransform: 'capitalize' },
  dayGroup: { gap: spacing.sm },
  day: { color: colors.muted, fontSize: 12, fontWeight: '800', textTransform: 'capitalize', marginTop: spacing.xs },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radii.lg, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, ...shadows.card },
  rowIcon: { flexShrink: 0, width: 36, height: 36, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  rowCopy: { flex: 1, minWidth: 0 },
  description: { color: colors.text, fontWeight: '800' },
  meta: { marginTop: 3, color: colors.muted, fontSize: 12 },
  rowEnd: { alignItems: 'flex-end', gap: 6 },
  amount: { fontWeight: '800', fontSize: 14 },
  actions: { flexDirection: 'row', gap: 12 },
});

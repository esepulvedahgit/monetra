import { useState } from 'react';
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { apiError } from '../../src/api/client';
import type { CartDetail, CartItem } from '../../src/api/types';
import { Loading, Screen } from '../../src/ui';
import { radii, shadows, spacing } from '../../src/theme/tokens';
import { useTheme, useThemedStyles, type ThemeColors } from '../../src/theme/theme';
import { useSession } from '../../src/auth/session';
import { AppHeader, EmptyState, ErrorState, PrimaryButton, SectionHeader } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';
import { CartItemEditor } from '../../src/features/cart/CartItemEditor';
import { CameraPermissionError, deleteTemporaryPhoto, takeLabelPhoto } from '../../src/features/cart/photo';
import { formatMoney, itemLabel, purchaseDate, recentStores, scanNotes, withTemporaryPhoto } from '../../src/features/cart/presentation';
import { useCartMutations, useCurrentCart, usePurchase, usePurchaseHistory, type CartEntry } from '../../src/features/cart/useCart';

export default function MarketScreen() {
  const { user } = useSession(); const symbol = user?.currency_symbol ?? '$';
  const current = useCurrentCart();
  const [finished, setFinished] = useState<CartDetail | null>(null);
  if (finished) return <PurchaseSummary cart={finished} symbol={symbol} onDone={() => setFinished(null)} />;
  if (current.isLoading) return <Loading />;
  if (current.isError) return <Screen refreshing={current.isFetching} onRefresh={() => void current.refetch()}><AppHeader /><ErrorState title="No pudimos cargar tu compra" onRetry={() => void current.refetch()} /></Screen>;
  if (current.data) return <Shopping cart={current.data} symbol={symbol} refreshing={current.isFetching} onRefresh={() => void current.refetch()} onFinished={setFinished} />;
  return <StartPurchase symbol={symbol} />;
}

function Heading({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  const styles = useThemedStyles(createStyles);
  return <View><Text style={styles.eyebrow}>{eyebrow}</Text><Text style={styles.title}>{title}</Text><Text style={styles.copy}>{copy}</Text></View>;
}

function StartPurchase({ symbol }: { symbol: string }) {
  const { colors } = useTheme(); const styles = useThemedStyles(createStyles);
  const history = usePurchaseHistory(); const mutations = useCartMutations();
  const [store, setStore] = useState(''); const [error, setError] = useState(''); const [viewing, setViewing] = useState<number | null>(null);
  const carts = history.data?.pages.flatMap((page) => page.carts) ?? [];
  const begin = async (name: string) => {
    if (mutations.start.isPending) return;
    if (!name.trim()) { setError('Escribe el nombre del supermercado.'); return; }
    setError('');
    try { await mutations.start.mutateAsync(name.trim()); } catch (exception) { setError(apiError(exception)); }
  };
  return <Screen refreshing={history.isFetching} onRefresh={() => void history.refetch()}>
    <AppHeader />
    <Heading eyebrow="Supermercado" title="Súper" copy="Fotografía cada etiqueta o escribe el producto y lleva el total del carro al día." />
    <View style={styles.card}>
      <Text style={styles.label}>¿En qué supermercado estás?</Text>
      <TextInput accessibilityLabel="Supermercado" value={store} onChangeText={setStore} placeholder="Ej. Lider" placeholderTextColor={colors.meta} selectionColor={colors.accent} returnKeyType="go" onSubmitEditing={() => void begin(store)} editable={!mutations.start.isPending} style={styles.input} />
      {recentStores(carts).length ? <View style={styles.chips}>{recentStores(carts).map((name) => <Pressable key={name} accessibilityRole="button" accessibilityLabel={`Empezar en ${name}`} disabled={mutations.start.isPending} onPress={() => { setStore(name); void begin(name); }} style={({ pressed }) => [styles.chip, pressed && styles.pressed]}><Text style={styles.chipText}>{name}</Text></Pressable>)}</View> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <PrimaryButton onPress={() => void begin(store)} loading={mutations.start.isPending} icon="cart">Empezar compra</PrimaryButton>
    </View>
    <SectionHeader title="Compras anteriores" />
    {history.isError ? <ErrorState title="No pudimos cargar tus compras" onRetry={() => void history.refetch()} /> : carts.length ? carts.map((cart) => (
      <Pressable key={cart.id} accessibilityRole="button" accessibilityLabel={`Compra en ${cart.store_name ?? 'supermercado'}, ${purchaseDate(cart)}, ${formatMoney(cart.total, symbol)}`} onPress={() => setViewing(cart.id)} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
        <View style={styles.rowIcon}><Icon name="cart" color={colors.accent} /></View>
        <View style={styles.rowCopy}><Text numberOfLines={1} style={styles.rowTitle}>{cart.store_name ?? 'Supermercado'}</Text><Text style={styles.meta}>{purchaseDate(cart)} · {cart.item_count} producto{cart.item_count === 1 ? '' : 's'}</Text></View>
        <Text style={styles.amount}>{formatMoney(cart.total, symbol)}</Text>
      </Pressable>
    )) : history.isLoading ? null : <EmptyState title="Sin compras todavía" copy="Cuando finalices una compra, verás aquí su fecha y su total." />}
    {history.hasNextPage ? <PrimaryButton variant="secondary" onPress={() => void history.fetchNextPage()} loading={history.isFetchingNextPage}>Cargar más compras</PrimaryButton> : null}
    <PurchaseSheet cartId={viewing} symbol={symbol} onClose={() => setViewing(null)} />
  </Screen>;
}

function Shopping({ cart, symbol, refreshing, onRefresh, onFinished }: { cart: CartDetail; symbol: string; refreshing: boolean; onRefresh: () => void; onFinished: (cart: CartDetail) => void }) {
  const { colors } = useTheme(); const styles = useThemedStyles(createStyles);
  const mutations = useCartMutations();
  const [last, setLast] = useState<CartEntry | null>(null); const [editorOpen, setEditorOpen] = useState(false);
  // Totals come from the latest server answer, which may be newer than the cached list.
  const total = last?.cart.id === cart.id ? last.cart.total : cart.total;
  const count = last?.cart.id === cart.id ? last.cart.item_count : cart.item_count;
  const lastItem: CartItem | undefined = last?.item ?? cart.items[cart.items.length - 1];
  const busy = mutations.scanAdd.isPending || mutations.removeItem.isPending || mutations.finalize.isPending || mutations.discard.isPending;

  const photo = async () => {
    if (busy) return;
    let uri: string | null;
    try { uri = await takeLabelPhoto(); } catch (exception) {
      Alert.alert('No pudimos abrir la cámara', exception instanceof CameraPermissionError ? exception.message : 'Inténtalo nuevamente o escribe el producto.');
      return;
    }
    if (!uri) return;
    try {
      setLast(await withTemporaryPhoto(uri, (photoUri) => mutations.scanAdd.mutateAsync({ cartId: cart.id, photoUri }), deleteTemporaryPhoto));
    } catch (exception) {
      Alert.alert('No se agregó el producto', `${apiError(exception)} Puedes intentarlo de nuevo o escribirlo.`);
    }
  };
  const removeLast = () => {
    if (!lastItem || busy) return;
    Alert.alert('Quitar último registro', `${itemLabel(lastItem)} — ${formatMoney(lastItem.line_total, symbol)}`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Quitar', style: 'destructive', onPress: () => void mutations.removeItem.mutateAsync({ cartId: cart.id, itemId: lastItem.id }).then(() => setLast(null)).catch((exception) => Alert.alert('No pudimos quitarlo', apiError(exception))) },
    ]);
  };
  const finish = () => {
    if (busy) return;
    if (!count) { Alert.alert('Carrito vacío', 'Agrega al menos un producto antes de finalizar.'); return; }
    Alert.alert('Finalizar compra', `Se guardará la compra en ${cart.store_name ?? 'el supermercado'} por ${formatMoney(total, symbol)}.`, [
      { text: 'Seguir comprando', style: 'cancel' },
      { text: 'Finalizar', onPress: () => void mutations.finalize.mutateAsync(cart.id).then(onFinished).catch((exception) => Alert.alert('No pudimos finalizar', apiError(exception))) },
    ]);
  };
  const cancel = () => {
    if (busy) return;
    const discard = () => void mutations.discard.mutateAsync(cart.id).catch((exception) => Alert.alert('No pudimos cancelarla', apiError(exception)));
    // An empty cart has nothing to lose.
    if (!count) { discard(); return; }
    Alert.alert('Cancelar compra', `Se eliminará la compra en ${cart.store_name ?? 'el supermercado'} con ${count} producto${count === 1 ? '' : 's'} (${formatMoney(total, symbol)}). No se puede deshacer.`, [
      { text: 'Seguir comprando', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: discard },
    ]);
  };

  return <Screen refreshing={refreshing} onRefresh={onRefresh}>
    <AppHeader />
    <Heading eyebrow="Compra en curso" title={cart.store_name ?? 'Supermercado'} copy="Cada producto se suma al instante. Si algo quedó mal, quita el último registro." />
    <View style={styles.totalCard} accessibilityLabel={`Total del carrito ${formatMoney(total, symbol)}, ${count} productos`}>
      <Text style={styles.totalLabel}>Total del carrito</Text>
      <Text style={styles.totalValue}>{formatMoney(total, symbol)}</Text>
      <Text style={styles.totalMeta}>{count} producto{count === 1 ? '' : 's'}</Text>
    </View>
    {lastItem ? <View style={styles.card}>
      <Text style={styles.label}>Último registro</Text>
      <View style={styles.lastLine}><Icon name="check" color={colors.success} size={18} /><Text numberOfLines={2} style={styles.lastName}>{itemLabel(lastItem)}</Text><Text style={styles.amount}>{formatMoney(lastItem.line_total, symbol)}</Text></View>
      {last?.item.id === lastItem.id ? scanNotes(last.scan, symbol).map((note) => <Text key={note} style={styles.note}>{note}</Text>) : null}
      <PrimaryButton variant="danger" icon="trash" onPress={removeLast} loading={mutations.removeItem.isPending}>Quitar último</PrimaryButton>
    </View> : null}
    <View style={styles.actions}>
      <Pressable accessibilityRole="button" accessibilityLabel="Fotografiar etiqueta" disabled={busy} onPress={() => void photo()} style={({ pressed }) => [styles.action, styles.actionPrimary, busy && styles.disabled, pressed && !busy && styles.pressed]}>
        <Icon name="camera" color={colors.onAccent} size={24} /><Text style={[styles.actionText, { color: colors.onAccent }]}>{mutations.scanAdd.isPending ? 'Leyendo etiqueta…' : 'Foto de etiqueta'}</Text>
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Escribir producto" disabled={busy} onPress={() => setEditorOpen(true)} style={({ pressed }) => [styles.action, busy && styles.disabled, pressed && !busy && styles.pressed]}>
        <Icon name="edit" size={24} /><Text style={styles.actionText}>Escribir</Text>
      </Pressable>
    </View>
    {cart.items.length ? <>
      <SectionHeader title="En el carrito" />
      {[...cart.items].reverse().map((item) => <ItemRow key={item.id} item={item} symbol={symbol} />)}
    </> : <EmptyState title="Carrito vacío" copy="Fotografía la etiqueta de precio o escribe el primer producto." />}
    <PrimaryButton icon="check" onPress={finish} loading={mutations.finalize.isPending}>Finalizar compra</PrimaryButton>
    <PrimaryButton icon="trash" variant="secondary" onPress={cancel}>Cancelar compra</PrimaryButton>
    <CartItemEditor visible={editorOpen} cartId={cart.id} onAdded={setLast} onClose={() => setEditorOpen(false)} />
  </Screen>;
}

function ItemRow({ item, symbol }: { item: CartItem; symbol: string }) {
  const styles = useThemedStyles(createStyles);
  return <View style={styles.itemRow}>
    <View style={styles.rowCopy}><Text numberOfLines={2} style={styles.itemName}>{itemLabel(item)}</Text>{item.qty !== 1 ? <Text style={styles.meta}>{formatMoney(item.unit_price, symbol)} c/u</Text> : null}</View>
    <Text style={styles.itemAmount}>{formatMoney(item.line_total, symbol)}</Text>
  </View>;
}

function ItemList({ cart, symbol }: { cart: CartDetail; symbol: string }) {
  const styles = useThemedStyles(createStyles);
  return <View style={styles.list}>
    {cart.items.map((item) => <ItemRow key={item.id} item={item} symbol={symbol} />)}
    <View style={styles.listTotal}><Text style={styles.listTotalLabel}>Total · {cart.item_count} producto{cart.item_count === 1 ? '' : 's'}</Text><Text style={styles.listTotalValue}>{formatMoney(cart.total, symbol)}</Text></View>
  </View>;
}

function PurchaseSummary({ cart, symbol, onDone }: { cart: CartDetail; symbol: string; onDone: () => void }) {
  return <Screen>
    <AppHeader />
    <Heading eyebrow="Compra guardada" title={cart.store_name ?? 'Supermercado'} copy={purchaseDate(cart)} />
    <ItemList cart={cart} symbol={symbol} />
    <PrimaryButton icon="check" onPress={onDone}>Listo</PrimaryButton>
  </Screen>;
}

function PurchaseSheet({ cartId, symbol, onClose }: { cartId: number | null; symbol: string; onClose: () => void }) {
  const styles = useThemedStyles(createStyles); const insets = useSafeAreaInsets();
  const purchase = usePurchase(cartId);
  return <Modal visible={cartId !== null} transparent animationType="slide" onRequestClose={onClose}>
    <View style={styles.backdrop}>
      <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md, paddingLeft: insets.left + spacing.lg, paddingRight: insets.right + spacing.lg }]}>
        <View style={styles.sheetHeader}>
          <View style={styles.rowCopy}><Text numberOfLines={1} style={styles.sheetTitle}>{purchase.data?.store_name ?? 'Compra'}</Text><Text style={styles.copy}>{purchase.data ? purchaseDate(purchase.data) : ''}</Text></View>
          <Pressable accessibilityLabel="Cerrar" onPress={onClose} style={({ pressed }) => [styles.close, pressed && styles.pressed]}><Icon name="close" /></Pressable>
        </View>
        <ScrollView contentContainerStyle={{ paddingTop: spacing.md }}>
          {purchase.data ? <ItemList cart={purchase.data} symbol={symbol} /> : purchase.isError ? <ErrorState title="No pudimos cargar la compra" onRetry={() => void purchase.refetch()} /> : <Text style={styles.copy}>Cargando…</Text>}
        </ScrollView>
      </View>
    </View>
  </Modal>;
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' },
  title: { color: colors.text, fontSize: 27, fontWeight: '800', marginTop: 4 },
  copy: { color: colors.muted, marginTop: 6, lineHeight: 20 },
  card: { gap: 10, padding: spacing.md, borderRadius: radii.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadows.card },
  label: { color: colors.text, fontSize: 13, fontWeight: '700' },
  input: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: 12, color: colors.text, fontSize: 16 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: { minHeight: 36, justifyContent: 'center', paddingHorizontal: 12, borderRadius: radii.pill, backgroundColor: colors.surfaceBlue },
  chipText: { color: colors.accent, fontWeight: '800', fontSize: 13 },
  error: { color: colors.danger, fontSize: 13 },
  pressed: { opacity: .82, transform: [{ scale: .97 }] },
  disabled: { opacity: .55 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radii.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadows.card },
  rowIcon: { flexShrink: 0, width: 36, height: 36, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceBlue },
  rowCopy: { flex: 1, minWidth: 0 },
  rowTitle: { color: colors.text, fontWeight: '800' },
  meta: { marginTop: 3, color: colors.muted, fontSize: 12 },
  amount: { color: colors.text, fontWeight: '800', fontSize: 14 },
  totalCard: { padding: 18, borderRadius: radii.lg, backgroundColor: colors.balanceSurface, borderWidth: 1, borderColor: colors.border },
  totalLabel: { color: colors.onBalanceMuted, fontSize: 13 },
  totalValue: { color: colors.onBalance, fontSize: 32, fontWeight: '800', marginTop: 2, fontVariant: ['tabular-nums'] },
  totalMeta: { color: colors.balancePositive, fontSize: 12, fontWeight: '700', marginTop: 4 },
  lastLine: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  lastName: { flex: 1, color: colors.text, fontWeight: '800', fontSize: 15 },
  note: { color: colors.warning, fontSize: 12, lineHeight: 17 },
  actions: { flexDirection: 'row', gap: 10 },
  action: { flex: 1, minHeight: 92, alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: radii.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  actionPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  actionText: { color: colors.text, fontWeight: '800', fontSize: 14 },
  itemRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.borderSoft },
  itemName: { color: colors.text, fontWeight: '700' },
  itemAmount: { color: colors.text, fontWeight: '800', fontVariant: ['tabular-nums'] },
  list: { paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderRadius: radii.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  listTotal: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12 },
  listTotalLabel: { color: colors.muted, fontWeight: '700' },
  listTotalValue: { color: colors.textStrong, fontWeight: '800', fontSize: 20, fontVariant: ['tabular-nums'] },
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: colors.scrim },
  sheet: { maxHeight: '85%', paddingTop: spacing.lg, backgroundColor: colors.card, borderTopLeftRadius: 22, borderTopRightRadius: 22 },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  sheetTitle: { color: colors.text, fontSize: 22, fontWeight: '800' },
  close: { flexShrink: 0, width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, backgroundColor: colors.surface },
});

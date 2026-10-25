import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { apiError } from '../../api/client';
import type { CartItemFormValues } from '../../api/types';
import { radii, spacing } from '../../theme/tokens';
import { useTheme, useThemedStyles, type ThemeColors } from '../../theme/theme';
import { Icon } from '../../components/Icon';
import { PrimaryButton } from '../../components/FinanceUi';
import { isCurrentEditorSubmission } from '../editorSafety';
import { buildCartItemPayload } from './presentation';
import { useCartMutations, type CartEntry } from './useCart';

const emptyValues: CartItemFormValues = { name: '', price: '', qty: '' };

/** Typed product. It is added right away: mobile carts have no confirmation step. */
export function CartItemEditor({ visible, cartId, onAdded, onClose }: { visible: boolean; cartId: number; onAdded: (entry: CartEntry) => void; onClose: () => void }) {
  const styles = useThemedStyles(createStyles); const mutations = useCartMutations(); const insets = useSafeAreaInsets();
  const editorSession = useRef(0); const visibleRef = useRef(visible);
  const [values, setValues] = useState<CartItemFormValues>(emptyValues); const [error, setError] = useState('');
  useEffect(() => {
    visibleRef.current = visible;
    if (visible) { editorSession.current += 1; setValues(emptyValues); setError(''); }
    return () => { editorSession.current += 1; visibleRef.current = false; };
  }, [visible]);
  const set = <K extends keyof CartItemFormValues>(key: K, value: CartItemFormValues[K]) => setValues((current) => ({ ...current, [key]: value }));
  const saving = mutations.addItem.isPending;
  const close = () => { if (!saving) onClose(); };
  const save = async () => {
    if (saving) return;
    const built = buildCartItemPayload(values);
    if ('error' in built) { setError(built.error); return; }
    const submissionSession = editorSession.current;
    try {
      const entry = await mutations.addItem.mutateAsync({ cartId, payload: built.payload });
      onAdded(entry);
      if (isCurrentEditorSubmission(submissionSession, editorSession.current, visibleRef.current)) onClose();
    } catch (exception) {
      if (isCurrentEditorSubmission(submissionSession, editorSession.current, visibleRef.current)) setError(apiError(exception));
    }
  };
  return <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
    <KeyboardAvoidingView style={styles.backdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'} keyboardVerticalOffset={insets.top}>
      <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md, paddingLeft: insets.left + spacing.lg, paddingRight: insets.right + spacing.lg }]}>
        <View style={styles.header}>
          <View style={styles.headerCopy}><Text numberOfLines={1} style={styles.title}>Escribir producto</Text><Text numberOfLines={2} style={styles.copy}>Se suma al carrito apenas lo guardas.</Text></View>
          <Pressable accessibilityLabel="Cerrar" disabled={saving} onPress={close} style={({ pressed }) => [styles.close, saving && styles.disabled, pressed && !saving && styles.pressed]}><Icon name="close" /></Pressable>
        </View>
        <ScrollView contentContainerStyle={[styles.form, { paddingBottom: insets.bottom + spacing.lg }]} keyboardDismissMode={Platform.OS === 'ios' ? 'interactive' : 'on-drag'} keyboardShouldPersistTaps="handled">
          <Field label="Producto" value={values.name} onChangeText={(value) => set('name', value)} placeholder="Ej. Leche entera 1L" editable={!saving} autoFocus />
          <View style={styles.row}>
            <View style={{ flex: 2 }}><Field label="Precio unitario" value={values.price} onChangeText={(value) => set('price', value)} placeholder="1.290" numeric editable={!saving} /></View>
            <View style={{ flex: 1 }}><Field label="Cantidad" value={values.qty} onChangeText={(value) => set('qty', value.replace(/\D/g, ''))} placeholder="1" integer editable={!saving} /></View>
          </View>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <PrimaryButton onPress={() => void save()} loading={saving} icon="plus">Agregar al carrito</PrimaryButton>
        </ScrollView>
      </View>
    </KeyboardAvoidingView>
  </Modal>;
}

function Field({ label, value, onChangeText, placeholder, numeric, integer, editable = true, autoFocus }: { label: string; value: string; onChangeText: (value: string) => void; placeholder: string; numeric?: boolean; integer?: boolean; editable?: boolean; autoFocus?: boolean }) {
  const { colors } = useTheme(); const styles = useThemedStyles(createStyles);
  return <View style={{ gap: 6 }}><Text style={styles.label}>{label}</Text><TextInput accessibilityLabel={label} autoFocus={autoFocus} editable={editable} value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={colors.meta} selectionColor={colors.accent} keyboardType={integer ? 'number-pad' : numeric ? 'decimal-pad' : 'default'} style={styles.input} /></View>;
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({ backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: colors.scrim }, sheet: { maxHeight: '90%', paddingVertical: spacing.lg, backgroundColor: colors.card, borderTopLeftRadius: 22, borderTopRightRadius: 22 }, header: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md }, headerCopy: { flex: 1, minWidth: 0 }, title: { color: colors.text, fontSize: 22, fontWeight: '800' }, copy: { color: colors.muted, marginTop: 5 }, close: { flexShrink: 0, width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, backgroundColor: colors.surface }, disabled: { opacity: .55 }, pressed: { opacity: .82, transform: [{ scale: .97 }] }, form: { gap: 12, paddingTop: spacing.lg }, row: { flexDirection: 'row', gap: 10 }, label: { color: colors.text, fontSize: 13, fontWeight: '700' }, input: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: 12, color: colors.text, fontSize: 16 }, error: { color: colors.danger, fontSize: 13 } });

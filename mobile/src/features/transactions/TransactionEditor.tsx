import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { Category, Transaction, TransactionFormValues } from '../../api/types';
import { apiError } from '../../api/client';
import { categoriesForType, buildTransactionPayload } from '../../finance/presentation';
import { colors, radii, spacing } from '../../theme/tokens';
import { Icon } from '../../components/Icon';
import { PrimaryButton } from '../../components/FinanceUi';
import { useTransactionMutations } from './useTransactionMutations';
import { isCurrentEditorSubmission, localDateString } from '../editorSafety';

type Props = { visible: boolean; transaction?: Transaction | null; categories: Category[]; onClose: () => void };
const today = () => localDateString();

export function TransactionEditor({ visible, transaction, categories, onClose }: Props) {
  const mutations = useTransactionMutations();
  const insets = useSafeAreaInsets();
  const editorSession = useRef(0);
  const visibleRef = useRef(visible);
  const [values, setValues] = useState<TransactionFormValues>({ type: 'expense', amount: '', date: today(), description: '', categoryId: '' });
  const [error, setError] = useState('');
  useEffect(() => {
    visibleRef.current = visible;
    if (visible) {
      editorSession.current += 1;
      setError('');
      setValues({ type: transaction?.type ?? 'expense', amount: transaction ? String(transaction.amount) : '', date: transaction?.date ?? today(), description: transaction?.description ?? '', categoryId: transaction?.category_id ? String(transaction.category_id) : '' });
    }
    return () => { editorSession.current += 1; visibleRef.current = false; };
  }, [visible, transaction]);
  const selectable = useMemo(() => categoriesForType(categories, values.type), [categories, values.type]);
  const saving = mutations.create.isPending || mutations.update.isPending;
  const set = <K extends keyof TransactionFormValues>(key: K, value: TransactionFormValues[K]) => setValues((current) => ({ ...current, [key]: value }));
  const close = () => { if (!saving) onClose(); };
  const save = async () => {
    if (saving) return;
    const payload = buildTransactionPayload(values);
    if (!payload.description || !payload.date || !Number.isFinite(payload.amount) || payload.amount <= 0) { setError('Completa descripción, monto válido y fecha.'); return; }
    const submissionSession = editorSession.current;
    try { if (transaction) await mutations.update.mutateAsync({ id: transaction.id, payload }); else await mutations.create.mutateAsync(payload); if (isCurrentEditorSubmission(submissionSession, editorSession.current, visibleRef.current)) onClose(); } catch (exception) { if (isCurrentEditorSubmission(submissionSession, editorSession.current, visibleRef.current)) setError(apiError(exception)); }
  };
  return <Modal visible={visible} transparent animationType="slide" onRequestClose={close}><KeyboardAvoidingView style={styles.backdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'} keyboardVerticalOffset={insets.top}><View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md, paddingLeft: insets.left + spacing.lg, paddingRight: insets.right + spacing.lg }]}><View style={styles.sheetHeader}><View style={styles.headerCopy}><Text style={styles.title} numberOfLines={1}>{transaction ? 'Editar movimiento' : 'Nuevo movimiento'}</Text><Text style={styles.copy} numberOfLines={2}>Registra un ingreso o gasto para actualizar tu resumen.</Text></View><Pressable disabled={saving} onPress={close} style={({ pressed }) => [styles.close, saving && styles.disabled, pressed && !saving && styles.pressed]}><Icon name="close" /></Pressable></View><ScrollView contentContainerStyle={[styles.form, { paddingBottom: insets.bottom + spacing.lg }]} keyboardDismissMode={Platform.OS === 'ios' ? 'interactive' : 'on-drag'} keyboardShouldPersistTaps="handled"><Text style={styles.label}>Tipo</Text><View style={styles.typeRow}>{(['expense', 'income'] as const).map((type) => <Pressable key={type} disabled={saving} onPress={() => setValues((current) => ({ ...current, type, categoryId: '' }))} style={({ pressed }) => [styles.typeButton, values.type === type && styles.typeButtonActive, pressed && !saving && styles.pressed]}><Icon name={type === 'expense' ? 'expense' : 'income'} color={values.type === type ? colors.onAccent : colors.text} size={17} /><Text style={[styles.typeText, values.type === type && styles.typeTextActive]}>{type === 'expense' ? 'Gasto' : 'Ingreso'}</Text></Pressable>)}</View><Text style={styles.label}>Categoría</Text><View style={styles.chips}>{selectable.map((category) => <Pressable key={category.id} disabled={saving} onPress={() => set('categoryId', String(category.id))} style={({ pressed }) => [styles.chip, values.categoryId === String(category.id) && { borderColor: category.color, backgroundColor: `${category.color}18` }, pressed && !saving && styles.pressed]}><View style={[styles.dot, { backgroundColor: category.color }]} /><Text style={styles.chipText}>{category.name}</Text></Pressable>)}</View><Text style={styles.label}>Descripción</Text><TextInput editable={!saving} value={values.description} onChangeText={(value) => set('description', value)} placeholder="Ej. Compra semanal" placeholderTextColor={colors.meta} selectionColor={colors.accent} style={styles.input} /><Text style={styles.label}>Monto</Text><TextInput editable={!saving} value={values.amount} onChangeText={(value) => set('amount', value)} keyboardType="decimal-pad" placeholder="0" placeholderTextColor={colors.meta} selectionColor={colors.accent} style={styles.input} /><Text style={styles.label}>Fecha</Text><TextInput editable={!saving} value={values.date} onChangeText={(value) => set('date', value)} placeholder="AAAA-MM-DD" placeholderTextColor={colors.meta} selectionColor={colors.accent} style={styles.input} />{error ? <Text style={styles.error}>{error}</Text> : null}<PrimaryButton onPress={() => void save()} loading={saving} icon="plus">Guardar movimiento</PrimaryButton></ScrollView></View></KeyboardAvoidingView></Modal>;
}

export function confirmDeleteTransaction(onConfirm: () => void) { Alert.alert('Eliminar movimiento', 'Esta acción no se puede deshacer.', [{ text: 'Cancelar', style: 'cancel' }, { text: 'Eliminar', style: 'destructive', onPress: onConfirm }]); }

const styles = StyleSheet.create({ backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(49,48,46,.35)' }, sheet: { maxHeight: '90%', paddingVertical: spacing.lg, backgroundColor: colors.background, borderTopLeftRadius: 22, borderTopRightRadius: 22 }, sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md }, headerCopy: { flex: 1, minWidth: 0 }, title: { color: colors.text, fontSize: 22, fontWeight: '800' }, copy: { marginTop: 5, color: colors.muted, fontSize: 13, lineHeight: 19 }, close: { flexShrink: 0, width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, backgroundColor: colors.surface }, disabled: { opacity: .55 }, pressed: { opacity: .82, transform: [{ scale: .97 }] }, form: { gap: 8, paddingTop: spacing.lg }, label: { marginTop: 7, color: colors.text, fontSize: 13, fontWeight: '700' }, typeRow: { flexDirection: 'row', gap: spacing.sm }, typeButton: { flex: 1, minHeight: 44, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6 }, typeButtonActive: { borderColor: colors.accent, backgroundColor: colors.accent }, typeText: { color: colors.text, fontWeight: '700' }, typeTextActive: { color: colors.onAccent }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, minHeight: 36, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.border }, dot: { width: 8, height: 8, borderRadius: radii.pill }, chipText: { color: colors.text, fontSize: 12, fontWeight: '700' }, input: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: 12, color: colors.text, fontSize: 16 }, error: { color: colors.danger, fontSize: 13, marginBottom: 4 }, });

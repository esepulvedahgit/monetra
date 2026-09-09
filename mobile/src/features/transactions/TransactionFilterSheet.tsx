import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { Category, Transaction } from '../../api/types';
import { Icon } from '../../components/Icon';
import { colors, radii, spacing } from '../../theme/tokens';

type Props = {
  visible: boolean;
  categories: Category[];
  type: 'all' | Transaction['type'];
  selectedCategoryId: number | null;
  onSelect: (categoryId: number | null) => void;
  onClose: () => void;
};

export function TransactionFilterSheet({ visible, categories, type, selectedCategoryId, onSelect, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const selectable = categories.filter((category) => type === 'all' || category.type === type);
  const select = (categoryId: number | null) => { onSelect(categoryId); onClose(); };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} accessibilityLabel="Cerrar filtros" onPress={onClose} />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md, paddingLeft: insets.left + spacing.lg, paddingRight: insets.right + spacing.lg }]}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <View>
              <Text style={styles.title}>Filtrar por categoría</Text>
              <Text style={styles.copy}>Elige una categoría para acotar los movimientos.</Text>
            </View>
            <Pressable accessibilityLabel="Cerrar filtros" hitSlop={10} onPress={onClose} style={({ pressed }) => [styles.close, pressed && styles.pressed]}>
              <Icon name="close" />
            </Pressable>
          </View>
          <ScrollView accessibilityRole="radiogroup" contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
            <Pressable accessibilityRole="radio" accessibilityState={{ selected: selectedCategoryId === null }} onPress={() => select(null)} style={({ pressed }) => [styles.option, pressed && styles.pressed]}>
              <View style={styles.optionCopy}>
                <View style={styles.allDot} />
                <Text style={styles.optionText}>Todas las categorías</Text>
              </View>
              {selectedCategoryId === null ? <Icon name="check" color={colors.accent} size={18} /> : null}
            </Pressable>
            {selectable.map((category) => (
              <Pressable key={category.id} accessibilityRole="radio" accessibilityState={{ selected: selectedCategoryId === category.id }} onPress={() => select(category.id)} style={({ pressed }) => [styles.option, pressed && styles.pressed]}>
                <View style={styles.optionCopy}>
                  <View style={[styles.dot, { backgroundColor: category.color }]} />
                  <Text style={styles.optionText}>{category.name}</Text>
                </View>
                {selectedCategoryId === category.id ? <Icon name="check" color={colors.accent} size={18} /> : null}
              </Pressable>
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(49,48,46,.28)' },
  sheet: { maxHeight: '76%', paddingTop: spacing.sm, backgroundColor: colors.background, borderTopLeftRadius: 24, borderTopRightRadius: 24 },
  handle: { alignSelf: 'center', width: 36, height: 4, borderRadius: radii.pill, backgroundColor: '#d8d4cf', marginBottom: spacing.md },
  header: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.borderSoft },
  title: { color: colors.text, fontSize: 20, fontWeight: '800' },
  copy: { color: colors.muted, fontSize: 13, marginTop: 4 },
  close: { width: 40, height: 40, borderRadius: radii.pill, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  list: { paddingTop: spacing.sm, paddingBottom: spacing.md },
  option: { minHeight: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.borderSoft },
  optionCopy: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  dot: { width: 10, height: 10, borderRadius: radii.pill },
  allDot: { width: 10, height: 10, borderRadius: radii.pill, backgroundColor: colors.meta },
  optionText: { color: colors.text, fontWeight: '700' },
  pressed: { opacity: .78, transform: [{ scale: .97 }] },
});

import { Pressable, StyleSheet, Text, View } from 'react-native';

import { radii, shadows, spacing } from '../theme/tokens';
import { useTheme, useThemedStyles, type ThemeColors, type ThemePreference } from '../theme/theme';
import { Icon, type IconName } from './Icon';

const options: { value: ThemePreference; label: string; icon: IconName }[] = [
  { value: 'system', label: 'Sistema', icon: 'device' },
  { value: 'light', label: 'Claro', icon: 'sun' },
  { value: 'dark', label: 'Oscuro', icon: 'moon' },
];

/** Segmented control for the app theme. The change applies instantly; it is rare enough not to animate. */
export function AppearancePicker() {
  const { colors, scheme, preference, setPreference } = useTheme();
  const styles = useThemedStyles(createStyles);
  return <View>
    <View accessibilityRole="radiogroup" accessibilityLabel="Apariencia" style={styles.track}>
      {options.map((option) => {
        const selected = option.value === preference;
        const tint = selected ? colors.accent : colors.muted;
        return <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ checked: selected }} accessibilityLabel={option.label} onPress={() => setPreference(option.value)} style={({ pressed }) => [styles.option, selected && styles.optionSelected, pressed && styles.pressed]}>
          <Icon name={option.icon} size={16} color={tint} />
          <Text style={[styles.label, { color: selected ? colors.text : colors.muted }]}>{option.label}</Text>
        </Pressable>;
      })}
    </View>
    <Text style={styles.caption}>{preference === 'system' ? `Sigue el tema del teléfono (ahora ${scheme === 'dark' ? 'oscuro' : 'claro'}).` : 'Se mantiene aunque cambie el tema del teléfono.'}</Text>
  </View>;
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  track: { flexDirection: 'row', padding: 3, gap: 3, borderRadius: radii.md, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border },
  option: { flex: 1, minHeight: 40, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 6 },
  optionSelected: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadows.card },
  pressed: { opacity: .85, transform: [{ scale: .97 }] },
  label: { fontSize: 13, fontWeight: '700' },
  caption: { color: colors.meta, fontSize: 12, lineHeight: 17, marginTop: spacing.sm },
});

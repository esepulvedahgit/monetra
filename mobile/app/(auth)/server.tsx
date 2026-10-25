import { useState } from 'react';
import { Alert, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';

import { probeServer } from '../../src/api/client';
import { useSession } from '../../src/auth/session';
import { suggestedServerUrl } from '../../src/config/serverConfig';
import { normalizeServerUrl, serverInputValue, serverLabel } from '../../src/config/serverUrl';
import { Card, Screen } from '../../src/ui';
import { radii, spacing } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/theme';
import { AppHeader, PrimaryButton } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';

export default function ServerScreen() {
  const { serverUrl, changeServer, user, locked } = useSession();
  const { colors } = useTheme();
  const initial = serverUrl ?? suggestedServerUrl;
  const [value, setValue] = useState(initial ? serverInputValue(initial) : '');
  const [busy, setBusy] = useState<'test' | 'save' | null>(null);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);

  const validate = async (): Promise<string | null> => {
    setStatus(null);
    let url: string;
    try { url = normalizeServerUrl(value, { allowHttp: __DEV__ }); } catch (error) { setStatus({ ok: false, message: (error as Error).message }); return null; }
    try { await probeServer(url); } catch (error) { setStatus({ ok: false, message: (error as Error).message }); return null; }
    setStatus({ ok: true, message: `Conexión correcta con ${serverLabel(url)}.` });
    return url;
  };

  const test = async () => {
    setBusy('test');
    try { await validate(); } finally { setBusy(null); }
  };

  const apply = async (url: string) => {
    await changeServer(url);
    router.replace('/(auth)/login');
  };

  const save = async () => {
    setBusy('save');
    try {
      const url = await validate();
      if (!url) return;
      if (url === serverUrl) { router.back(); return; }
      if (user || locked) {
        Alert.alert('Cambiar servidor', 'Se cerrará la sesión en este teléfono y tendrás que ingresar en el nuevo servidor.', [
          { text: 'Cancelar', style: 'cancel' },
          { text: 'Cambiar', style: 'destructive', onPress: () => void apply(url).catch(() => Alert.alert('No fue posible guardar el servidor', 'Inténtalo nuevamente.')) },
        ]);
        return;
      }
      await apply(url);
    } catch {
      Alert.alert('No fue posible guardar el servidor', 'Inténtalo nuevamente.');
    } finally {
      setBusy(null);
    }
  };

  return <Screen><AppHeader action="close" onAction={() => router.canGoBack() ? router.back() : router.replace('/')} /><View style={styles.hero}><View style={[styles.icon, { backgroundColor: colors.surfaceBlue }]}><Icon name="server" color={colors.accent} size={28} /></View><Text style={[styles.title, { color: colors.text }]}>Servidor</Text><Text style={[styles.copy, { color: colors.muted }]}>Dirección HTTPS de tu instalación de Monetra.</Text></View>
    <Card><Text style={[styles.label, { color: colors.muted }]}>Dirección del servidor</Text><TextInput value={value} onChangeText={(text) => { setValue(text); setStatus(null); }} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="https://monetra.midominio.com" placeholderTextColor={colors.meta} style={[styles.input, { borderColor: colors.border, color: colors.text, backgroundColor: colors.background }]} />{serverUrl ? <Text style={[styles.note, { color: colors.meta }]}>Actual: {serverLabel(serverUrl)}</Text> : null}</Card>
    {status ? <Text style={[styles.status, { color: status.ok ? colors.success : colors.danger }]}>{status.message}</Text> : null}
    <PrimaryButton onPress={() => void test()} loading={busy === 'test'} icon="check" variant="secondary">Probar conexión</PrimaryButton>
    <PrimaryButton onPress={() => void save()} loading={busy === 'save'} icon="server">Guardar servidor</PrimaryButton>
  </Screen>;
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', marginTop: spacing.lg, marginBottom: spacing.md },
  icon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 27, fontWeight: '800', marginTop: spacing.md },
  copy: { textAlign: 'center', lineHeight: 21, marginTop: spacing.sm, maxWidth: 330 },
  label: { fontWeight: '700', marginBottom: spacing.sm },
  input: { borderWidth: 1, borderRadius: radii.md, padding: spacing.md, fontSize: 16 },
  note: { marginTop: spacing.sm },
  status: { textAlign: 'center', lineHeight: 20 },
});

import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';

import { useSession } from '../../src/auth/session';
import { apiError } from '../../src/api/client';
import { Card, Screen } from '../../src/ui';
import { spacing } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/theme';
import { AppHeader, PrimaryButton } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';

export default function UnlockScreen() {
  const { unlockQuickAccess, signOut } = useSession();
  const { colors } = useTheme();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const unlock = async () => {
    setError(null);
    setBusy(true);
    try {
      await unlockQuickAccess();
      router.replace('/(tabs)/summary');
    } catch (reason) {
      if ((reason as { code?: string }).code !== 'CANCELLED') setError(apiError(reason));
    } finally {
      setBusy(false);
    }
  };

  const usePassword = async () => {
    await signOut();
    router.replace('/(auth)/login');
  };

  return <Screen><AppHeader /><View style={styles.hero}><View style={[styles.icon, { backgroundColor: colors.surfaceBlue }]}><Icon name="lock" color={colors.accent} size={30} /></View><Text style={[styles.title, { color: colors.text }]}>Sesión bloqueada</Text><Text style={[styles.copy, { color: colors.muted }]}>Desbloquea con la huella, rostro, PIN, patrón o contraseña configurados en este teléfono.</Text></View><Card><Text style={[styles.note, { color: colors.muted }]}>Monetra no conoce ni guarda la credencial de desbloqueo de tu dispositivo.</Text></Card>{error ? <Text style={[styles.error, { color: colors.danger }]}>{error}</Text> : null}<PrimaryButton onPress={() => void unlock()} loading={busy} icon="lock">Desbloquear con mi teléfono</PrimaryButton><PrimaryButton onPress={() => void usePassword()} loading={busy} icon="user" variant="secondary">Ingresar con correo y contraseña</PrimaryButton></Screen>;
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', marginTop: spacing.xl, marginBottom: spacing.lg },
  icon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 27, fontWeight: '800', marginTop: spacing.md },
  copy: { textAlign: 'center', lineHeight: 21, marginTop: spacing.sm, maxWidth: 330 },
  note: { lineHeight: 20 },
  error: { marginVertical: spacing.md, textAlign: 'center' },
});

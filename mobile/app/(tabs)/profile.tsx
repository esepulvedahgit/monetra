import { Alert, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';

import { useSession } from '../../src/auth/session';
import { Card, Screen } from '../../src/ui';
import { colors, spacing } from '../../src/theme/tokens';
import { AppHeader, PrimaryButton } from '../../src/components/FinanceUi';
import { Icon } from '../../src/components/Icon';

export default function ProfileScreen() {
  const { user, signOut, quickAccessSupported, quickAccessEnabled, enableQuickAccess, disableQuickAccess } = useSession();

  const logout = () => Alert.alert('Cerrar sesión', 'Tendrás que volver a ingresar en este dispositivo.', [
    { text: 'Cancelar', style: 'cancel' },
    { text: 'Cerrar sesión', style: 'destructive', onPress: () => void signOut().then(() => router.replace('/(auth)/login')) },
  ]);
  const configureQuickAccess = () => {
    const action = quickAccessEnabled ? disableQuickAccess : enableQuickAccess;
    const title = quickAccessEnabled ? 'Desactivar acceso rápido' : 'Activar acceso rápido';
    const message = quickAccessEnabled
      ? 'Volverás a ingresar con correo y contraseña después de 15 minutos sin actividad.'
      : 'Después de 15 minutos sin actividad, desbloquearás Monetra con la credencial de este teléfono.';
    Alert.alert(title, message, [
      { text: 'Cancelar', style: 'cancel' },
      { text: quickAccessEnabled ? 'Desactivar' : 'Activar', onPress: () => void action().catch(() => Alert.alert('No fue posible actualizar el acceso rápido', 'Revisa el bloqueo de pantalla del teléfono e inténtalo nuevamente.')) },
    ]);
  };

  return <Screen><AppHeader /><Text style={styles.eyebrow}>Tu cuenta</Text><Text style={styles.title}>Perfil</Text><Card><View style={styles.person}><View style={styles.avatar}><Icon name="user" color={colors.accent} size={25} /></View><View><Text style={styles.name}>{user?.name}</Text><Text style={styles.email}>{user?.email}</Text></View></View><View style={styles.details}><Text style={styles.detail}>País: {user?.country || 'No indicado'}</Text><Text style={styles.detail}>Moneda: {user?.currency_code} ({user?.currency_symbol})</Text><Text style={styles.detail}>Idioma: {user?.language === 'en' ? 'English' : 'Español'}</Text></View></Card>{quickAccessSupported ? <Card><View style={styles.security}><View><Text style={styles.securityTitle}>Acceso rápido</Text><Text style={styles.detail}>{quickAccessEnabled ? 'Usa el bloqueo de este teléfono después de 15 minutos.' : 'Desbloquea con el PIN, patrón, contraseña o biometría del teléfono.'}</Text></View><Icon name="lock" color={colors.accent} size={22} /></View><PrimaryButton onPress={configureQuickAccess} icon="lock" variant="secondary">{quickAccessEnabled ? 'Desactivar acceso rápido' : 'Activar acceso rápido'}</PrimaryButton></Card> : <Card><Text style={styles.detail}>El acceso rápido requiere Android 11 o superior y un bloqueo de pantalla configurado.</Text></Card>}<PrimaryButton onPress={() => router.push('/(auth)/change-password')} icon="edit" variant="secondary">Cambiar contraseña</PrimaryButton><PrimaryButton onPress={logout} icon="close" variant="danger">Cerrar sesión</PrimaryButton></Screen>;
}

const styles = StyleSheet.create({
  eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase', marginTop: spacing.sm },
  title: { color: colors.text, fontSize: 27, fontWeight: '800', marginTop: 4 },
  person: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 52, height: 52, alignItems: 'center', justifyContent: 'center', borderRadius: 26, backgroundColor: colors.surfaceBlue },
  name: { color: colors.text, fontSize: 19, fontWeight: '800' },
  email: { color: colors.muted, marginTop: 3 },
  details: { marginTop: spacing.md, gap: 4 },
  detail: { color: colors.muted, lineHeight: 20 },
  security: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  securityTitle: { color: colors.text, fontWeight: '800', fontSize: 16, marginBottom: 4 },
});

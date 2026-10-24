import { useState } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, apiError, probeServer } from '../../src/api/client';
import type { User } from '../../src/api/types';
import { useSession } from '../../src/auth/session';
import { applyServerUrl, saveServerUrl, suggestedServerUrl } from '../../src/config/serverConfig';
import { normalizeServerUrl, serverInputValue, serverLabel } from '../../src/config/serverUrl';
import { radii, spacing } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/theme';
import { Icon } from '../../src/components/Icon';

export default function Login() {
  const { reason } = useLocalSearchParams<{ reason?: string }>();
  const { signIn, serverUrl } = useSession();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const firstRun = !serverUrl;
  const [server, setServer] = useState(suggestedServerUrl ? serverInputValue(suggestedServerUrl) : '');
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [passwordVisible, setPasswordVisible] = useState(false); const [loading, setLoading] = useState(false);
  const submit = async () => {
    if (firstRun && !server.trim()) return Alert.alert('Ingresa la dirección de tu servidor');
    if (!email || !password) return Alert.alert('Completa correo y contraseña');
    let pendingServer: string | null = null;
    if (firstRun) {
      try { pendingServer = normalizeServerUrl(server, { allowHttp: __DEV__ }); } catch (error) { return Alert.alert('Servidor no válido', (error as Error).message); }
    }
    setLoading(true);
    try {
      if (pendingServer) {
        try { await probeServer(pendingServer); } catch (error) { Alert.alert('No pudimos validar el servidor', (error as Error).message); return; }
        // Tried for this login only; it is stored once the server accepts the credentials.
        applyServerUrl(pendingServer);
      }
      const response = await api.post('/login', { email, password });
      if (pendingServer) await saveServerUrl(pendingServer);
      pendingServer = null;
      if (response.status === 202) { router.push({ pathname: '/(auth)/mfa', params: { token: response.data.mfa_token } }); return; }
      await signIn({ accessToken: response.data.access_token, refreshToken: response.data.refresh_token, quickAccessStatusToken: response.data.quick_access_status_token }, response.data.user as User);
      router.replace('/(tabs)/summary');
    } catch (error) {
      Alert.alert('No pudimos iniciar sesión', apiError(error));
    } finally {
      if (pendingServer) applyServerUrl(null);
      setLoading(false);
    }
  };
  return <View style={{ flex: 1, justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background }}>
    {!firstRun ? <Pressable accessibilityRole="button" accessibilityLabel="Configurar servidor" accessibilityHint="Edita el servidor al que se conecta Monetra" hitSlop={8} onPress={() => router.push('/(auth)/server')} style={({ pressed }) => [serverButton, { top: insets.top + spacing.md, borderColor: colors.border, backgroundColor: colors.surface }, pressed && pressedToggle]}><Icon name="server" color={colors.muted} size={18} /><Text style={{ color: colors.muted, fontWeight: '600' }}>Servidor</Text></Pressable> : null}
    <Image source={require('../../assets/monetra-logo.png')} accessibilityLabel="Monetra" resizeMode="contain" style={{ width: 220, height: 145, alignSelf: 'center', marginBottom: spacing.md }} />
    <Text style={{ color: colors.textStrong, fontSize: 32, fontWeight: '800' }}>Monetra</Text><Text style={{ color: colors.muted, marginTop: spacing.sm, marginBottom: spacing.xl }}>{firstRun ? 'Conecta la app con tu servidor Monetra.' : 'Tus finanzas, más simples.'}</Text>
    {reason === 'session_expired' ? <Text style={{ color: colors.warning, marginBottom: spacing.md }}>Tu sesión expiró. Inicia sesión nuevamente.</Text> : null}
    {reason === 'quick_access_unavailable' ? <Text style={{ color: colors.warning, marginBottom: spacing.md }}>No pudimos recuperar el acceso rápido en este teléfono. Inicia sesión para configurarlo nuevamente.</Text> : null}
    {firstRun
      ? <TextInput value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="Servidor (https://monetra.midominio.com)" placeholderTextColor={colors.meta} style={[input, { borderColor: colors.border, color: colors.text }]} />
      : <Text numberOfLines={1} style={{ color: colors.meta, marginBottom: spacing.md }}>Conectado a {serverLabel(serverUrl)}</Text>}
    <TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="Correo electrónico" placeholderTextColor={colors.meta} style={[input, { borderColor: colors.border, color: colors.text }]} />
    <View style={passwordField}><TextInput value={password} onChangeText={setPassword} secureTextEntry={!passwordVisible} placeholder="Contraseña" placeholderTextColor={colors.meta} style={[passwordInput, { borderColor: colors.border, color: colors.text }]} /><Pressable accessibilityRole="button" accessibilityLabel={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'} accessibilityHint="Cambia la visibilidad de la contraseña" hitSlop={8} onPress={() => setPasswordVisible((visible) => !visible)} style={({ pressed }) => [passwordToggle, pressed && pressedToggle]}><Icon name={passwordVisible ? 'eye-off' : 'eye'} color={colors.muted} /></Pressable></View>
    <Pressable onPress={submit} disabled={loading} style={[button, { backgroundColor: colors.accent }]}>{loading ? <ActivityIndicator color={colors.onAccent} /> : <Text style={[buttonText, { color: colors.onAccent }]}>{firstRun ? 'Conectar e iniciar sesión' : 'Iniciar sesión'}</Text>}</Pressable>
    <Text style={{ color: colors.meta, textAlign: 'center', marginTop: spacing.lg }}>{firstRun ? 'Usa la dirección HTTPS de tu instalación de Monetra.' : 'La recuperación abre el enlace seguro enviado a tu correo.'}</Text>
  </View>;
}
const input = { borderWidth: 1, borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.md, fontSize: 16 } as const;
const passwordField = { position: 'relative', marginBottom: spacing.md } as const;
const passwordInput = { ...input, marginBottom: 0, paddingRight: 52 } as const;
const passwordToggle = { position: 'absolute', right: spacing.sm, top: 0, bottom: 0, width: 44, alignItems: 'center', justifyContent: 'center' } as const;
const pressedToggle = { opacity: .7, transform: [{ scale: .97 }] } as const;
const serverButton = { position: 'absolute', right: spacing.xl, flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderRadius: radii.md, paddingHorizontal: spacing.md, minHeight: 40 } as const;
const button = { borderRadius: radii.md, minHeight: 52, alignItems: 'center', justifyContent: 'center' } as const;
const buttonText = { fontWeight: '700', fontSize: 16 } as const;

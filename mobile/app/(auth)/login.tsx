import { useState } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { api, apiError } from '../../src/api/client';
import type { User } from '../../src/api/types';
import { useSession } from '../../src/auth/session';
import { radii, spacing } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/theme';
import { Icon } from '../../src/components/Icon';

export default function Login() {
  const { reason } = useLocalSearchParams<{ reason?: string }>();
  const { signIn } = useSession();
  const { colors } = useTheme();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [passwordVisible, setPasswordVisible] = useState(false); const [loading, setLoading] = useState(false);
  const submit = async () => {
    if (!email || !password) return Alert.alert('Completa correo y contraseña');
    setLoading(true);
    try {
      const response = await api.post('/login', { email, password });
      if (response.status === 202) { router.push({ pathname: '/(auth)/mfa', params: { token: response.data.mfa_token } }); return; }
      await signIn({ accessToken: response.data.access_token, refreshToken: response.data.refresh_token, quickAccessStatusToken: response.data.quick_access_status_token }, response.data.user as User);
      router.replace('/(tabs)/summary');
    } catch (error) { Alert.alert('No pudimos iniciar sesión', apiError(error)); } finally { setLoading(false); }
  };
  return <View style={{ flex: 1, justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background }}>
    <Image source={require('../../assets/monetra-logo.png')} accessibilityLabel="Monetra" resizeMode="contain" style={{ width: 220, height: 145, alignSelf: 'center', marginBottom: spacing.md }} />
    <Text style={{ color: colors.textStrong, fontSize: 32, fontWeight: '800' }}>Monetra</Text><Text style={{ color: colors.muted, marginTop: spacing.sm, marginBottom: spacing.xl }}>Tus finanzas, más simples.</Text>
    {reason === 'session_expired' ? <Text style={{ color: colors.warning, marginBottom: spacing.md }}>Tu sesión expiró. Inicia sesión nuevamente.</Text> : null}
    {reason === 'quick_access_unavailable' ? <Text style={{ color: colors.warning, marginBottom: spacing.md }}>No pudimos recuperar el acceso rápido en este teléfono. Inicia sesión para configurarlo nuevamente.</Text> : null}
    <TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="Correo electrónico" placeholderTextColor={colors.meta} style={[input, { borderColor: colors.border, color: colors.text }]} />
    <View style={passwordField}><TextInput value={password} onChangeText={setPassword} secureTextEntry={!passwordVisible} placeholder="Contraseña" placeholderTextColor={colors.meta} style={[passwordInput, { borderColor: colors.border, color: colors.text }]} /><Pressable accessibilityRole="button" accessibilityLabel={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'} accessibilityHint="Cambia la visibilidad de la contraseña" hitSlop={8} onPress={() => setPasswordVisible((visible) => !visible)} style={({ pressed }) => [passwordToggle, pressed && pressedToggle]}><Icon name={passwordVisible ? 'eye-off' : 'eye'} color={colors.muted} /></Pressable></View>
    <Pressable onPress={submit} disabled={loading} style={[button, { backgroundColor: colors.accent }]}>{loading ? <ActivityIndicator color={colors.onAccent} /> : <Text style={[buttonText, { color: colors.onAccent }]}>Iniciar sesión</Text>}</Pressable>
    <Text style={{ color: colors.meta, textAlign: 'center', marginTop: spacing.lg }}>La recuperación abre el enlace seguro enviado a tu correo.</Text>
  </View>;
}
const input = { borderWidth: 1, borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.md, fontSize: 16 } as const;
const passwordField = { position: 'relative', marginBottom: spacing.md } as const;
const passwordInput = { ...input, marginBottom: 0, paddingRight: 52 } as const;
const passwordToggle = { position: 'absolute', right: spacing.sm, top: 0, bottom: 0, width: 44, alignItems: 'center', justifyContent: 'center' } as const;
const pressedToggle = { opacity: .7, transform: [{ scale: .97 }] } as const;
const button = { borderRadius: radii.md, minHeight: 52, alignItems: 'center', justifyContent: 'center' } as const;
const buttonText = { fontWeight: '700', fontSize: 16 } as const;

import { useState } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';

import { api, apiError } from '../../src/api/client';
import type { User } from '../../src/api/types';
import { useSession } from '../../src/auth/session';
import { colors, radii, spacing } from '../../src/theme/tokens';
import { Icon } from '../../src/components/Icon';

export default function Login() {
  const { signIn } = useSession();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [passwordVisible, setPasswordVisible] = useState(false); const [loading, setLoading] = useState(false);
  const submit = async () => {
    if (!email || !password) return Alert.alert('Completa correo y contraseña');
    setLoading(true);
    try {
      const response = await api.post('/login', { email, password });
      if (response.status === 202) { router.push({ pathname: '/(auth)/mfa', params: { token: response.data.mfa_token } }); return; }
      await signIn({ accessToken: response.data.access_token, refreshToken: response.data.refresh_token }, response.data.user as User);
      router.replace('/(tabs)/summary');
    } catch (error) { Alert.alert('No pudimos iniciar sesión', apiError(error)); } finally { setLoading(false); }
  };
  return <View style={{ flex: 1, justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background }}>
    <Image source={require('../../assets/monetra-logo.png')} accessibilityLabel="Monetra" resizeMode="contain" style={{ width: 220, height: 145, alignSelf: 'center', marginBottom: spacing.md }} />
    <Text style={{ color: colors.textStrong, fontSize: 32, fontWeight: '800' }}>Monetra</Text><Text style={{ color: colors.muted, marginTop: spacing.sm, marginBottom: spacing.xl }}>Tus finanzas, más simples.</Text>
    <TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="Correo electrónico" style={input} />
    <View style={passwordField}><TextInput value={password} onChangeText={setPassword} secureTextEntry={!passwordVisible} placeholder="Contraseña" style={passwordInput} /><Pressable accessibilityRole="button" accessibilityLabel={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'} accessibilityHint="Cambia la visibilidad de la contraseña" hitSlop={8} onPress={() => setPasswordVisible((visible) => !visible)} style={({ pressed }) => [passwordToggle, pressed && pressedToggle]}><Icon name={passwordVisible ? 'eye-off' : 'eye'} color={colors.muted} /></Pressable></View>
    <Pressable onPress={submit} disabled={loading} style={button}>{loading ? <ActivityIndicator color={colors.onAccent} /> : <Text style={buttonText}>Iniciar sesión</Text>}</Pressable>
    <Text style={{ color: colors.meta, textAlign: 'center', marginTop: spacing.lg }}>La recuperación abre el enlace seguro enviado a tu correo.</Text>
  </View>;
}
const input = { borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.md, color: colors.text, fontSize: 16 } as const;
const passwordField = { position: 'relative', marginBottom: spacing.md } as const;
const passwordInput = { ...input, marginBottom: 0, paddingRight: 52 } as const;
const passwordToggle = { position: 'absolute', right: spacing.sm, top: 0, bottom: 0, width: 44, alignItems: 'center', justifyContent: 'center' } as const;
const pressedToggle = { opacity: .7, transform: [{ scale: .97 }] } as const;
const button = { backgroundColor: colors.accent, borderRadius: radii.md, minHeight: 52, alignItems: 'center', justifyContent: 'center' } as const;
const buttonText = { color: colors.onAccent, fontWeight: '700', fontSize: 16 } as const;

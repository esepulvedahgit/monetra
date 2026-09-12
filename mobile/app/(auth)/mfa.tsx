import { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { api, apiError } from '../../src/api/client';
import type { User } from '../../src/api/types';
import { useSession } from '../../src/auth/session';
import { radii, spacing } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/theme';

export default function Mfa() {
  const { token } = useLocalSearchParams<{ token: string }>(); const { signIn } = useSession();
  const { colors } = useTheme();
  const [code, setCode] = useState(''); const [loading, setLoading] = useState(false);
  const verify = async () => { setLoading(true); try {
    const response = await api.post('/mfa/verify', { mfa_token: token, code });
    await signIn({ accessToken: response.data.access_token, refreshToken: response.data.refresh_token, quickAccessStatusToken: response.data.quick_access_status_token }, response.data.user as User);
    router.replace('/(tabs)/summary');
  } catch (error) { Alert.alert('Código inválido', apiError(error)); } finally { setLoading(false); } };
  return <View style={{ flex: 1, justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background }}>
    <Text style={{ color: colors.textStrong, fontSize: 26, fontWeight: '800' }}>Verificación en dos pasos</Text><Text style={{ color: colors.muted, marginVertical: spacing.lg }}>Ingresa el código de tu aplicación autenticadora.</Text>
    <TextInput value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} autoFocus placeholderTextColor={colors.meta} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, padding: spacing.md, fontSize: 24, letterSpacing: 8, color: colors.text }} />
    <Pressable style={{ backgroundColor: colors.accent, borderRadius: radii.md, padding: spacing.md, alignItems: 'center', marginTop: spacing.md }} onPress={verify}>{loading ? <ActivityIndicator color={colors.onAccent} /> : <Text style={{ color: colors.onAccent, fontWeight: '700' }}>Verificar</Text>}</Pressable>
  </View>;
}

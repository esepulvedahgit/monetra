import { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { api, apiError } from '../../src/api/client';
import { useSession } from '../../src/auth/session';
import { colors, radii, spacing } from '../../src/theme/tokens';

export default function ChangePassword() {
  const { signOut } = useSession();
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirm, setConfirm] = useState(''); const [loading, setLoading] = useState(false);
  const submit = async () => { setLoading(true); try {
    await api.post('/me/password', { current_password: current, new_password: next, confirm_password: confirm });
    await signOut(); Alert.alert('Contraseña actualizada', 'Vuelve a iniciar sesión.'); router.replace('/(auth)/login');
  } catch (error) { Alert.alert('No pudimos actualizarla', apiError(error)); } finally { setLoading(false); } };
  return <View style={{ flex: 1, justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background }}><Text style={{ fontSize: 26, fontWeight: '800', color: colors.textStrong, marginBottom: spacing.lg }}>Cambiar contraseña</Text>
    <TextInput secureTextEntry value={current} onChangeText={setCurrent} placeholder="Contraseña actual" style={input} /><TextInput secureTextEntry value={next} onChangeText={setNext} placeholder="Nueva contraseña" style={input} /><TextInput secureTextEntry value={confirm} onChangeText={setConfirm} placeholder="Confirmar contraseña" style={input} />
    <Text style={{ color: colors.meta, marginBottom: spacing.md }}>Mínimo 10 caracteres, mayúscula, minúscula, número y símbolo.</Text><Pressable onPress={submit} style={button}>{loading ? <ActivityIndicator color={colors.onAccent} /> : <Text style={{ color: colors.onAccent, fontWeight: '700' }}>Actualizar contraseña</Text>}</Pressable>
  </View>;
}
const input = { borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.md, color: colors.text } as const;
const button = { backgroundColor: colors.accent, borderRadius: radii.md, padding: spacing.md, alignItems: 'center' } as const;

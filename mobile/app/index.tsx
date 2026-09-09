import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { router } from 'expo-router';
import { useSession } from '../src/auth/session';
import { colors } from '../src/theme/tokens';

export default function Index() {
  const { ready, user } = useSession();
  useEffect(() => { if (ready) router.replace(user ? '/(tabs)/summary' : '/(auth)/login'); }, [ready, user]);
  return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><ActivityIndicator color={colors.accent} /></View>;
}

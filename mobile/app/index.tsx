import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { router } from 'expo-router';
import { useSession } from '../src/auth/session';
import { useTheme } from '../src/theme/theme';

export default function Index() {
  const { ready, user, locked } = useSession();
  const { colors } = useTheme();
  useEffect(() => { if (ready) router.replace(locked ? '/(auth)/unlock' : user ? '/(tabs)/summary' : '/(auth)/login'); }, [ready, locked, user]);
  return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><ActivityIndicator color={colors.accent} /></View>;
}

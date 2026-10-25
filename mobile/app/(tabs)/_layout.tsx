import { useQuery } from '@tanstack/react-query';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTheme } from '../../src/theme/theme';
import { Icon } from '../../src/components/Icon';
import { mobileTabBarLayout } from '../../src/layout/mobileLayout';
import { api } from '../../src/api/client';
import type { User } from '../../src/api/types';
import { useSession } from '../../src/auth/session';

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { user } = useSession();
  // Súper needs the user's own AI or the one the admin shares; it is re-checked on each mount.
  const me = useQuery({ queryKey: ['me'], queryFn: async () => (await api.get<User>('/me')).data });
  const marketAvailable = (me.data ?? user)?.cart_scanner_available === true;
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: colors.accent, tabBarInactiveTintColor: colors.meta, tabBarStyle: { borderTopColor: colors.border, backgroundColor: colors.card, ...mobileTabBarLayout(insets.bottom) }, tabBarLabelStyle: { fontWeight: '700', fontSize: 10 }, sceneStyle: { backgroundColor: colors.background } }}>
    <Tabs.Screen name="summary" options={{ title: 'Resumen', tabBarIcon: ({ color, size }) => <Icon name="grid" color={color as string} size={size} /> }} />
    <Tabs.Screen name="transactions" options={{ title: 'Movimientos', tabBarIcon: ({ color, size }) => <Icon name="arrows" color={color as string} size={size} /> }} />
    <Tabs.Screen name="market" options={{ title: 'Súper', href: marketAvailable ? undefined : null, tabBarIcon: ({ color, size }) => <Icon name="cart" color={color as string} size={size} /> }} />
    <Tabs.Screen name="goals" options={{ title: 'Metas', tabBarIcon: ({ color, size }) => <Icon name="target" color={color as string} size={size} /> }} />
    <Tabs.Screen name="profile" options={{ title: 'Perfil', tabBarIcon: ({ color, size }) => <Icon name="user" color={color as string} size={size} /> }} />
  </Tabs>;
}

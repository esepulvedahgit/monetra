import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors } from '../../src/theme/tokens';
import { Icon } from '../../src/components/Icon';
import { mobileTabBarLayout } from '../../src/layout/mobileLayout';

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: colors.accent, tabBarInactiveTintColor: colors.meta, tabBarStyle: { borderTopColor: colors.border, backgroundColor: colors.background, ...mobileTabBarLayout(insets.bottom) }, tabBarLabelStyle: { fontWeight: '700', fontSize: 10 } }}>
    <Tabs.Screen name="summary" options={{ title: 'Resumen', tabBarIcon: ({ color, size }) => <Icon name="grid" color={color as string} size={size} /> }} />
    <Tabs.Screen name="transactions" options={{ title: 'Movimientos', tabBarIcon: ({ color, size }) => <Icon name="arrows" color={color as string} size={size} /> }} />
    <Tabs.Screen name="goals" options={{ title: 'Metas', tabBarIcon: ({ color, size }) => <Icon name="target" color={color as string} size={size} /> }} />
    <Tabs.Screen name="profile" options={{ title: 'Perfil', tabBarIcon: ({ color, size }) => <Icon name="user" color={color as string} size={size} /> }} />
  </Tabs>;
}

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { I18nextProvider } from 'react-i18next';
import { StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { SessionProvider } from '../src/auth/session';
import { i18n } from '../src/i18n';
import { ThemeProvider, useTheme } from '../src/theme/theme';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

function ThemedStack() {
  const { scheme, colors } = useTheme();
  return <>
    <StatusBar barStyle={scheme === 'dark' ? 'light-content' : 'dark-content'} backgroundColor="transparent" translucent />
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }} />
  </>;
}

export default function RootLayout() {
  return <SafeAreaProvider><ThemeProvider><I18nextProvider i18n={i18n}><QueryClientProvider client={queryClient}><SessionProvider>
    <ThemedStack />
  </SessionProvider></QueryClientProvider></I18nextProvider></ThemeProvider></SafeAreaProvider>;
}

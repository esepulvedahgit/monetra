import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { I18nextProvider } from 'react-i18next';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { SessionProvider } from '../src/auth/session';
import { i18n } from '../src/i18n';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

export default function RootLayout() {
  return <SafeAreaProvider><I18nextProvider i18n={i18n}><QueryClientProvider client={queryClient}><SessionProvider>
    <Stack screenOptions={{ headerShown: false }} />
  </SessionProvider></QueryClientProvider></I18nextProvider></SafeAreaProvider>;
}

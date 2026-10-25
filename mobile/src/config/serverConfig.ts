import AsyncStorage from '@react-native-async-storage/async-storage';

const serverKey = 'monetra.mobile.server.v1';

let currentServerUrl: string | null = null;
const listeners = new Set<(url: string | null) => void>();

/** Build-time hint only: prefills the first-run form but never configures the app by itself. */
export const suggestedServerUrl = process.env.EXPO_PUBLIC_API_URL ?? '';

function publish(url: string | null): void {
  currentServerUrl = url;
  listeners.forEach((listener) => listener(url));
}

export function getServerUrl(): string | null {
  return currentServerUrl;
}

export async function loadServerUrl(): Promise<string | null> {
  try {
    publish(await AsyncStorage.getItem(serverKey));
  } catch {
    publish(null);
  }
  return currentServerUrl;
}

/** Points requests at a server for this process only, e.g. while a first login is being tried. */
export function applyServerUrl(url: string | null): void {
  publish(url);
}

export async function saveServerUrl(url: string): Promise<void> {
  await AsyncStorage.setItem(serverKey, url);
  publish(url);
}

export function subscribeServerUrl(listener: (url: string | null) => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

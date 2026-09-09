import * as SecureStore from 'expo-secure-store';

const tokenKey = 'monetra.mobile.tokens.v1';
export type Tokens = { accessToken: string; refreshToken: string };

export async function getTokens(): Promise<Tokens | null> {
  const raw = await SecureStore.getItemAsync(tokenKey);
  if (!raw) return null;
  try { return JSON.parse(raw) as Tokens; } catch { return null; }
}
export async function setTokens(tokens: Tokens): Promise<void> { await SecureStore.setItemAsync(tokenKey, JSON.stringify(tokens)); }
export async function clearTokens(): Promise<void> { await SecureStore.deleteItemAsync(tokenKey); }

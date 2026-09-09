import * as SecureStore from 'expo-secure-store';
import { QuickAccessTokenStore, type QuickAccessVault } from './quickAccessTokenStore';

const tokenKey = 'monetra.mobile.tokens.v1';
export type Tokens = { accessToken: string; refreshToken: string };

const regularTokens = {
  async get(): Promise<Tokens | null> {
  const raw = await SecureStore.getItemAsync(tokenKey);
  if (!raw) return null;
  try { return JSON.parse(raw) as Tokens; } catch { return null; }
  },
  async set(tokens: Tokens): Promise<void> { await SecureStore.setItemAsync(tokenKey, JSON.stringify(tokens)); },
  async clear(): Promise<void> { await SecureStore.deleteItemAsync(tokenKey); },
};

const unavailableVault: QuickAccessVault = {
  enroll: async () => { throw new Error('El acceso rápido no está disponible.'); },
  rotate: async () => { throw new Error('El acceso rápido no está disponible.'); },
  lock: async () => undefined,
  clear: async () => undefined,
};
const quickAccessTokens = new QuickAccessTokenStore(regularTokens, unavailableVault);

export const getTokens = () => quickAccessTokens.get();
export const setTokens = (tokens: Tokens) => quickAccessTokens.set(tokens);
export const clearTokens = () => quickAccessTokens.clear();
export const enableQuickAccess = (tokens: Tokens) => quickAccessTokens.enable(tokens);
export const unlockQuickAccess = (tokens: Tokens) => quickAccessTokens.unlock(tokens);
export const lockQuickAccess = () => quickAccessTokens.lock();
export const disableQuickAccess = () => quickAccessTokens.disable();
export const markQuickAccessLocked = () => quickAccessTokens.markLocked();
export const isQuickAccessEnabled = () => quickAccessTokens.isQuickAccessEnabled();
export const configureQuickAccessVault = (vault: QuickAccessVault) => quickAccessTokens.setVault(vault);

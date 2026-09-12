import * as SecureStore from 'expo-secure-store';
import { QuickAccessTokenStore, type QuickAccessVault } from './quickAccessTokenStore';

const tokenKey = 'monetra.mobile.tokens.v1';
export type Tokens = {
  accessToken: string;
  refreshToken: string;
  // Optional while devices migrate from sessions issued before this field existed.
  quickAccessStatusToken?: string;
};

let activeRegularTokens: Tokens | null = null;
let legacyTokensDiscarded = false;

/**
 * Sessions without quick access must not survive an Android process restart.
 * Older releases persisted these tokens, so discard them without ever reading
 * or restoring their value.
 */
async function discardLegacyTokens(): Promise<void> {
  if (legacyTokensDiscarded) return;
  legacyTokensDiscarded = true;
  try { await SecureStore.deleteItemAsync(tokenKey); } catch { /* Legacy data is never read. */ }
}

const regularTokens = {
  async get(): Promise<Tokens | null> {
    await discardLegacyTokens();
    return activeRegularTokens;
  },
  async set(tokens: Tokens): Promise<void> {
    await discardLegacyTokens();
    activeRegularTokens = tokens;
  },
  async clear(): Promise<void> {
    activeRegularTokens = null;
    try { await SecureStore.deleteItemAsync(tokenKey); } catch { /* Best-effort legacy cleanup. */ }
  },
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

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { currentTokenSession, getSessionTokens, isCurrentTokenSession, setSessionTokens } from '../auth/sessionTokens';
import { notifySessionExpired } from '../auth/sessionExpiry';
import { shouldEndSessionAfterRefreshFailure } from '../auth/refreshFailure';
import { isReadCacheKey, readCacheKey } from './readCache';
import { ApiSession, type ApiSessionBinding } from './requestSession';

const baseURL = process.env.EXPO_PUBLIC_API_URL ?? 'https://monetra.hgrey.net/api/v1';

export const api = axios.create({
  baseURL,
  timeout: 15_000,
  headers: {
    common: { Accept: 'application/json' },
    post: { 'Content-Type': 'application/json' },
  },
});
type CachedRequest = InternalAxiosRequestConfig & { _session?: ApiSessionBinding; _tokenSession?: number; _retried?: boolean };

const apiSession = new ApiSession();
const staleSessionError = () => new Error('La sesión cambió antes de completar la solicitud.');

export function setReadCacheAccount(accountId: number | null): void {
  apiSession.begin(accountId);
}

export async function clearReadCache(): Promise<void> {
  try {
    const keys = (await AsyncStorage.getAllKeys()).filter(isReadCacheKey);
    if (keys.length) await AsyncStorage.multiRemove(keys);
  } catch { /* cache is optional */ }
}

function cacheKey(config: CachedRequest): string {
  return readCacheKey(config.url ?? '', config.params, config._session?.accountId ?? null);
}

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const request = config as CachedRequest;
  request._session ??= apiSession.capture();
  request._tokenSession ??= currentTokenSession();
  const tokens = await getSessionTokens();
  if (!apiSession.isCurrent(request._session) || !isCurrentTokenSession(request._tokenSession)) throw staleSessionError();
  if (tokens?.accessToken && !request.headers.Authorization) request.headers.Authorization = `Bearer ${tokens.accessToken}`;
  return request;
});

let refreshing: { session: ApiSessionBinding; promise: Promise<string | null> } | undefined;

async function refreshAccessToken(session: ApiSessionBinding, tokenSession: number): Promise<string | null> {
  const tokens = await getSessionTokens();
  if (!tokens?.refreshToken || !apiSession.isCurrent(session) || !isCurrentTokenSession(tokenSession)) return null;
  try {
    const response = await axios.post(`${baseURL}/refresh`, undefined, {
      headers: { Authorization: `Bearer ${tokens.refreshToken}` }, timeout: 15_000,
    });
    if (!apiSession.isCurrent(session) || !isCurrentTokenSession(tokenSession)) return null;
    const accessToken = response.data.access_token as string;
    try {
      const wrote = await setSessionTokens(tokenSession, { accessToken, refreshToken: response.data.refresh_token });
      return wrote && apiSession.isCurrent(session) ? accessToken : null;
    } catch {
      // Refresh rotation is one-time. If its replacement cannot be sealed locally,
      // end the session instead of leaving an apparently-open session with no token.
      if (apiSession.isCurrent(session) && isCurrentTokenSession(tokenSession)) notifySessionExpired(tokenSession);
      return null;
    }
  } catch (error) {
    if (shouldEndSessionAfterRefreshFailure(error) && apiSession.isCurrent(session) && isCurrentTokenSession(tokenSession)) {
      notifySessionExpired(tokenSession);
    }
    return null;
  }
}

api.interceptors.response.use(async (response) => {
  const request = response.config as CachedRequest;
  if (!request._session || !apiSession.isCurrent(request._session) || !isCurrentTokenSession(request._tokenSession ?? -1)) return Promise.reject(staleSessionError());
  if (response.config.method?.toLowerCase() === 'get') {
    try { await AsyncStorage.setItem(cacheKey(response.config), JSON.stringify(response.data)); } catch { /* cache is optional */ }
  }
  return response;
}, async (error: AxiosError) => {
  const request = error.config as CachedRequest | undefined;
  if (request?._session && (!apiSession.isCurrent(request._session) || !isCurrentTokenSession(request._tokenSession ?? -1))) return Promise.reject(staleSessionError());
  if (request?.method?.toLowerCase() === 'get' && !error.response) {
    try {
      const cached = await AsyncStorage.getItem(cacheKey(request));
      if (cached) return { data: JSON.parse(cached), status: 200, statusText: 'Offline cache', headers: {}, config: request };
    } catch { /* no cache available */ }
  }
  if (error.response?.status !== 401 || !request || request._retried || request.url === '/refresh') return Promise.reject(error);
  request._retried = true;
  const session = request._session ?? apiSession.capture();
  const tokenSession = request._tokenSession ?? currentTokenSession();
  if (!session.accountId || !apiSession.canRetry(session) || !isCurrentTokenSession(tokenSession)) return Promise.reject(staleSessionError());
  if (!refreshing || refreshing.session.generation !== session.generation) {
    const promise = refreshAccessToken(session, tokenSession).finally(() => {
      if (refreshing?.session.generation === session.generation) refreshing = undefined;
    });
    refreshing = { session, promise };
  }
  const accessToken = await refreshing.promise;
  if (!accessToken || !apiSession.canRetry(session) || !isCurrentTokenSession(tokenSession)) return Promise.reject(staleSessionError());
  request.headers.Authorization = `Bearer ${accessToken}`;
  return api.request(request);
});

export function apiError(error: unknown): string {
  const response = error as AxiosError<{ message?: string; error?: string }>;
  const serverMessage = response.response?.data?.message ?? response.response?.data?.error;
  if (serverMessage) return serverMessage;
  if (response.code === 'ECONNABORTED' || response.code === 'ETIMEDOUT') {
    return 'La conexión con Monetra tardó demasiado. Inténtalo nuevamente.';
  }
  if (!response.response && (response.code === 'ERR_NETWORK' || response.message === 'Network Error')) {
    return 'No se pudo conectar con Monetra. Revisa tu conexión e inténtalo nuevamente.';
  }
  return 'No fue posible completar la solicitud.';
}

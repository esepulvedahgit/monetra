const cachePrefix = 'monetra.mobile.read-cache.v1';

export function readCacheKey(url: string, params: unknown, accountId: number | null): string {
  return `${cachePrefix}:${accountId ?? 'anonymous'}:${url}?${JSON.stringify(params ?? {})}`;
}

export function isReadCacheKey(key: string): boolean {
  return key.startsWith(`${cachePrefix}:`);
}

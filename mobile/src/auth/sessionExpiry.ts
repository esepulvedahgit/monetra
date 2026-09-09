type SessionExpiryListener = (tokenSession: number) => void;

const listeners = new Set<SessionExpiryListener>();

export function subscribeSessionExpiry(listener: SessionExpiryListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notifySessionExpired(tokenSession: number): void {
  listeners.forEach((listener) => listener(tokenSession));
}

import type { Tokens } from './tokens';

export type TokenPersistence = {
  get: () => Promise<Tokens | null>;
  set: (tokens: Tokens) => Promise<void>;
  clear: () => Promise<void>;
};

export type QuickAccessVault = {
  enroll: (refreshToken: string, quickAccessStatusToken?: string) => Promise<void>;
  rotate: (refreshToken: string, quickAccessStatusToken?: string) => Promise<void>;
  lock: () => Promise<void>;
  clear: () => Promise<void>;
};

/**
 * Keeps a quick-access session exclusively in memory. The vault retains only an
 * Android-Keystore-encrypted refresh token, never the access token or user data.
 */
export class QuickAccessTokenStore {
  private quickAccessEnabled = false;
  private activeTokens: Tokens | null = null;

  constructor(private readonly regular: TokenPersistence, private vault: QuickAccessVault) {}

  setVault(vault: QuickAccessVault): void {
    this.vault = vault;
  }

  async get(): Promise<Tokens | null> {
    return this.quickAccessEnabled ? this.activeTokens : this.regular.get();
  }

  async set(tokens: Tokens): Promise<void> {
    if (!this.quickAccessEnabled) return this.regular.set(tokens);
    if (!this.activeTokens) throw new Error('Quick access is locked.');
    await this.vault.rotate(tokens.refreshToken, tokens.quickAccessStatusToken);
    this.activeTokens = tokens;
  }

  async enable(tokens: Tokens): Promise<void> {
    await this.vault.enroll(tokens.refreshToken, tokens.quickAccessStatusToken);
    try {
      await this.regular.clear();
    } catch (error) {
      await this.vault.clear();
      throw error;
    }
    this.quickAccessEnabled = true;
    this.activeTokens = tokens;
  }

  /** Restores memory after a successful system-credential unlock. */
  async unlock(tokens: Tokens): Promise<void> {
    await this.vault.rotate(tokens.refreshToken, tokens.quickAccessStatusToken);
    this.quickAccessEnabled = true;
    this.activeTokens = tokens;
  }

  async lock(): Promise<void> {
    if (!this.quickAccessEnabled) return;
    this.activeTokens = null;
    await this.vault.lock();
  }

  async disable(): Promise<void> {
    if (!this.quickAccessEnabled) return;
    if (!this.activeTokens) throw new Error('Unlock quick access before disabling it.');
    await this.regular.set(this.activeTokens);
    await this.vault.clear();
    this.activeTokens = null;
    this.quickAccessEnabled = false;
  }

  async clear(): Promise<void> {
    this.activeTokens = null;
    this.quickAccessEnabled = false;
    await Promise.all([this.regular.clear(), this.vault.clear()]);
  }

  markLocked(): void {
    this.quickAccessEnabled = true;
    this.activeTokens = null;
  }

  isQuickAccessEnabled(): Promise<boolean> {
    return Promise.resolve(this.quickAccessEnabled);
  }
}

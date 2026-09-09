import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const mobileRoot = resolve(import.meta.dirname, '..');
const source = (path: string) => readFileSync(resolve(mobileRoot, path), 'utf8');

describe('quick access security contract', () => {
  it('uses an authenticated Android Keystore wrapping key and treats durable writes as mandatory', () => {
    const vault = source('android/app/src/main/java/com/monetra/mobile/DeviceCredentialVaultModule.kt');

    expect(vault).toContain('AUTH_BIOMETRIC_STRONG or KeyProperties.AUTH_DEVICE_CREDENTIAL');
    expect(vault).toContain('if (!stored) throw IllegalStateException');
    expect(vault).toContain('operationGeneration += 1');
    expect(vault).toContain('generation != operationGeneration || cancellation.isCanceled');
  });
});

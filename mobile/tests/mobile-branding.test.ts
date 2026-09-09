import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const mobileRoot = resolve(import.meta.dirname, '..');

function source(path: string) {
  return readFileSync(resolve(mobileRoot, path), 'utf8');
}

describe('mobile branding', () => {
  it('uses the Monetra app emblem in the shared header', () => {
    const header = source('src/components/FinanceUi.tsx');

    expect(header).toContain("require('../../assets/monetra-app-icon.png')");
    expect(header).not.toContain('<Icon name="wallet" size={18}');
  });

  it('keeps one movement creation action next to the title', () => {
    const screen = source('app/(tabs)/transactions.tsx');

    expect(screen).not.toContain('action="plus" onAction={openCreate}');
    expect(screen.match(/accessibilityLabel="Agregar movimiento"/g)).toHaveLength(1);
    expect(screen).not.toContain('>Agregar movimiento</PrimaryButton>');
  });
});

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

import type { Cart } from '../src/api/types';
import { buildCartItemPayload, formatMoney, itemLabel, newRequestKey, parseCartAmount, parseServerDate, photoResize, purchaseDate, recentStores, scanNotes, withTemporaryPhoto } from '../src/features/cart/presentation';

const mobileRoot = resolve(import.meta.dirname, '..');
const source = (path: string) => readFileSync(resolve(mobileRoot, path), 'utf8');

const cart = (id: number, store: string | null): Cart => ({ id, status: 'finalized', store_name: store, total: 1000, item_count: 1, source: 'api', started_at: null, updated_at: null, finalized_at: null });

describe('parseCartAmount', () => {
  it.each([
    ['1290', 1290], ['1.290', 1290], ['$ 1.290', 1290], ['12.500.000', 12500000],
    ['1.290,50', 1290.5], ['3.50', 3.5], ['3,5', 3.5],
  ])('reads %s', (input, expected) => {
    expect(parseCartAmount(input)).toBe(expected);
  });

  it.each(['', 'abc', '0', '-5', '1.2.3', '12,345,6', '1290x'])('rejects %s', (input) => {
    expect(parseCartAmount(input)).toBeNull();
  });
});

describe('buildCartItemPayload', () => {
  it('sends the unit price and quantity, defaulting to one', () => {
    expect(buildCartItemPayload({ name: ' Leche ', price: '1.290', qty: '' })).toEqual({ payload: { name: 'Leche', qty: 1, unit_price: 1290 } });
    expect(buildCartItemPayload({ name: 'Yogurt', price: '990', qty: '2' })).toEqual({ payload: { name: 'Yogurt', qty: 2, unit_price: 990 } });
  });

  it('explains what is missing', () => {
    expect(buildCartItemPayload({ name: '', price: '990', qty: '' })).toEqual({ error: 'Escribe el nombre del producto.' });
    expect(buildCartItemPayload({ name: 'Pan', price: 'gratis', qty: '' })).toEqual({ error: 'Ingresa un precio válido.' });
    expect(buildCartItemPayload({ name: 'Pan', price: '990', qty: '0' })).toHaveProperty('error');
    expect(buildCartItemPayload({ name: 'Pan', price: '990', qty: '1000' })).toHaveProperty('error');
  });
});

describe('recentStores', () => {
  it('keeps the most recent spelling of each store, ignoring case and accents', () => {
    expect(recentStores([cart(5, 'Lider'), cart(4, null), cart(3, 'LÍDER'), cart(2, 'Jumbo'), cart(1, 'Unimarc')], 2)).toEqual(['Lider', 'Jumbo']);
  });
});

describe('photoResize', () => {
  it('limits the longest side and leaves small photos as they are', () => {
    expect(photoResize(4000, 3000)).toEqual({ width: 1600 });
    expect(photoResize(3000, 4000)).toEqual({ height: 1600 });
    expect(photoResize(1200, 1600)).toBeNull();
  });
});

describe('withTemporaryPhoto', () => {
  it('deletes the photo after a successful upload', async () => {
    const remove = vi.fn();
    await expect(withTemporaryPhoto('file:///cache/a.jpg', async () => 'ok', remove)).resolves.toBe('ok');
    expect(remove).toHaveBeenCalledWith('file:///cache/a.jpg');
  });

  it('deletes the photo when the upload fails and keeps the upload error', async () => {
    const remove = vi.fn(() => { throw new Error('already gone'); });
    await expect(withTemporaryPhoto('file:///cache/b.jpg', async () => { throw new Error('price_not_found'); }, remove)).rejects.toThrow('price_not_found');
    expect(remove).toHaveBeenCalledOnce();
  });
});

describe('presentation', () => {
  it('formats amounts and quantities', () => {
    expect(formatMoney(15480, '$')).toBe('$15.480');
    expect(itemLabel({ name: 'Yogurt', qty: 2 })).toBe('2 × Yogurt');
    expect(itemLabel({ name: 'Pan', qty: 1 })).toBe('Pan');
  });

  it('explains offers and per-kg prices read from a label', () => {
    const notes = scanNotes({ name: 'Aceite', price: 3990, offer_price: 3490, offer_text: 'Con tarjeta', unit: 'kg' }, '$');
    expect(notes[0]).toContain('Oferta $3.490 (Con tarjeta)');
    expect(notes[1]).toContain('Precio por kg');
    expect(scanNotes(null, '$')).toEqual([]);
  });

  it('reads server dates without an offset as UTC', () => {
    expect(parseServerDate('2026-10-25T01:30:00').toISOString()).toBe('2026-10-25T01:30:00.000Z');
    expect(parseServerDate('2026-10-25T01:30:00+00:00').toISOString()).toBe('2026-10-25T01:30:00.000Z');
    // 01:30 UTC is still the evening of the 24th in Santiago.
    expect(purchaseDate({ finalized_at: '2026-10-25T01:30:00', started_at: null }, 'America/Santiago')).toBe('24 de octubre de 2026');
  });

  it('creates a different idempotency key for every product', () => {
    expect(newRequestKey()).not.toBe(newRequestKey());
  });
});

describe('mobile cart contract', () => {
  it('adds scanned labels without a confirmation step and never creates a finance movement', () => {
    const hooks = source('src/features/cart/useCart.ts');
    expect(hooks).toContain('/scan?add=1');
    expect(hooks).toContain("'Idempotency-Key': newRequestKey()");
    expect(hooks).toContain('register_movement: false');
  });

  it('cancels a purchase by deleting the cart, asking first only when it has products', () => {
    expect(source('src/features/cart/useCart.ts')).toContain('api.delete(`/carts/${cartId}`)');
    const screen = source('app/(tabs)/market.tsx');
    expect(screen).toContain('if (!count) { discard(); return; }');
    expect(screen).toContain('Cancelar compra');
  });

  it('deletes every temporary photo, the original capture included', () => {
    expect(source('app/(tabs)/market.tsx')).toContain('withTemporaryPhoto(uri, (photoUri) => mutations.scanAdd.mutateAsync({ cartId: cart.id, photoUri }), deleteTemporaryPhoto)');
    expect(source('src/features/cart/photo.ts')).toMatch(/finally \{\s*try \{ deleteFile\(capture\.uri\); \}/);
  });

  it('only shows Súper when the account can use AI', () => {
    expect(source('app/(tabs)/_layout.tsx')).toContain("href: marketAvailable ? undefined : null");
  });

  it('asks only for the camera permission', () => {
    const app = JSON.parse(source('app.json'));
    const picker = app.expo.plugins.find((plugin: unknown) => Array.isArray(plugin) && plugin[0] === 'expo-image-picker');
    expect(picker[1]).toMatchObject({ microphonePermission: false, photosPermission: false });
    expect(source('android/app/src/main/AndroidManifest.xml')).toContain('android.permission.RECORD_AUDIO" tools:node="remove"');
  });
});

import type { Cart, CartItemFormValues, CartScan } from '../../api/types';

export const PHOTO_MAX_SIDE = 1600;
export const STEPPER_MAX_QTY = 99;
const MAX_QTY = 999;

/**
 * Reads a price as typed at the store: `1290`, `1.290`, `$1.290`, `1.290,50` or `3.50`.
 * A dot followed by exactly three digits is a thousands separator; a comma is decimal.
 */
export function parseCartAmount(input: string): number | null {
  const text = input.replace(/[\s$]/g, '');
  if (!/^\d[\d.,]*$/.test(text)) return null;
  let normalized: string;
  if (text.includes(',')) {
    normalized = text.replace(/\./g, '').replace(',', '.');
  } else if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
    normalized = text.replace(/\./g, '');
  } else {
    normalized = text;
  }
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  const amount = Number(normalized);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

/** Validated body for `POST /carts/{id}/items`, or a message for the form. */
export function buildCartItemPayload(values: CartItemFormValues): { payload: { name: string; qty: number; unit_price: number } } | { error: string } {
  const name = values.name.trim();
  if (!name) return { error: 'Escribe el nombre del producto.' };
  if (name.length > 200) return { error: 'El nombre es demasiado largo.' };
  const price = parseCartAmount(values.price);
  if (price === null) return { error: 'Ingresa un precio válido.' };
  const qtyText = values.qty.trim();
  const qty = qtyText ? Number(qtyText) : 1;
  if (!Number.isInteger(qty) || qty < 1 || qty > MAX_QTY) return { error: 'La cantidad debe ser un número entero entre 1 y 999.' };
  return { payload: { name, qty, unit_price: price } };
}

/** Units chosen with the − / + buttons, kept between 1 and STEPPER_MAX_QTY. */
export function clampQty(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.min(STEPPER_MAX_QTY, Math.max(1, Math.round(value)));
}

/** Distinct store names of past carts, most recent first, as shortcuts to start a new one. */
export function recentStores(carts: Cart[], limit = 4): string[] {
  const seen = new Set<string>();
  const stores: string[] = [];
  for (const cart of carts) {
    const name = cart.store_name?.trim();
    const key = name?.toLocaleLowerCase('es').normalize('NFD').replace(/[̀-ͯ]/g, '');
    if (!name || !key || seen.has(key)) continue;
    seen.add(key);
    stores.push(name);
    if (stores.length === limit) break;
  }
  return stores;
}

/** Resize that keeps the longest side within PHOTO_MAX_SIDE, or null when the photo already fits. */
export function photoResize(width: number, height: number): { width: number } | { height: number } | null {
  if (Math.max(width, height) <= PHOTO_MAX_SIDE) return null;
  return width >= height ? { width: PHOTO_MAX_SIDE } : { height: PHOTO_MAX_SIDE };
}

/** Runs `upload` with a temporary photo and always deletes it afterwards, even when the upload fails. */
export async function withTemporaryPhoto<T>(uri: string, upload: (uri: string) => Promise<T>, remove: (uri: string) => void | Promise<void>): Promise<T> {
  try {
    return await upload(uri);
  } finally {
    try { await remove(uri); } catch { /* The OS clears the cache directory eventually. */ }
  }
}

/** One key per product sent, so a retried request never adds it twice. */
export function newRequestKey(): string {
  return `mobile-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function formatMoney(value: number, symbol: string): string {
  return `${symbol}${value.toLocaleString('es-CL', { maximumFractionDigits: 2 })}`;
}

export function itemLabel(item: { name: string; qty: number }): string {
  return item.qty === 1 ? item.name : `${item.qty} × ${item.name}`;
}

/** Notes shown under the last product read from a label, since it was added without confirmation. */
export function scanNotes(scan: CartScan | null | undefined, symbol: string): string[] {
  if (!scan) return [];
  const notes: string[] = [];
  if (scan.offer_price !== null) {
    const condition = scan.offer_text ? ` (${scan.offer_text})` : '';
    notes.push(`Oferta ${formatMoney(scan.offer_price, symbol)}${condition}. Se sumó el precio normal; si pagas la oferta, quita este registro y escríbela.`);
  }
  if (scan.unit === 'kg') notes.push('Precio por kg: si pesaste el producto, quita este registro y escribe el monto de la balanza.');
  return notes;
}

/** Date of the purchase: when it was finalized, or when it started if it is still open. */
export function purchaseDate(cart: Pick<Cart, 'finalized_at' | 'started_at'>, timeZone?: string): string {
  const value = cart.finalized_at ?? cart.started_at;
  if (!value) return '';
  return new Intl.DateTimeFormat('es-CL', { day: 'numeric', month: 'long', year: 'numeric', timeZone }).format(parseServerDate(value));
}

/** The server stores UTC and may omit the offset; without it JS would read the time as local. */
export function parseServerDate(value: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`);
}

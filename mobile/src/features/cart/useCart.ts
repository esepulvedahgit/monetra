import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';
import type { Cart, CartDetail, CartItem, CartScan } from '../../api/types';
import { newRequestKey } from './presentation';

export type CartPage = { carts: Cart[]; has_next: boolean };
export type CartEntry = { item: CartItem; cart: Cart; scan?: CartScan | null };

// Reading a label with AI takes longer than a regular request.
const SCAN_TIMEOUT_MS = 60_000;

export const currentCartKey = ['cart', 'current'] as const;

export function useCurrentCart() {
  return useQuery({ queryKey: currentCartKey, queryFn: async () => (await api.get<{ cart: CartDetail | null }>('/carts/current')).data.cart });
}

export function usePurchaseHistory() {
  return useInfiniteQuery({
    queryKey: ['carts', 'finalized'],
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => (await api.get<CartPage>('/carts', { params: { status: 'finalized', page: pageParam, per_page: 30 } })).data,
    getNextPageParam: (lastPage, pages) => lastPage.has_next ? pages.length + 1 : undefined,
  });
}

export function usePurchase(cartId: number | null) {
  return useQuery({ queryKey: ['cart', cartId], enabled: cartId !== null, queryFn: async () => (await api.get<CartDetail>(`/carts/${cartId}`)).data });
}

export function useCartMutations() {
  const client = useQueryClient();
  const setCurrent = (cart: CartDetail | null) => client.setQueryData(currentCartKey, cart);
  // Every entry returns the new total; the item list is refreshed from the server.
  const refreshCurrent = () => client.invalidateQueries({ queryKey: currentCartKey });

  const start = useMutation({
    mutationFn: async (storeName: string) => (await api.post<CartDetail>('/carts', { store_name: storeName })).data,
    onSuccess: setCurrent,
  });
  const addItem = useMutation({
    mutationFn: async ({ cartId, payload }: { cartId: number; payload: { name: string; qty: number; unit_price: number } }) =>
      (await api.post<CartEntry>(`/carts/${cartId}/items`, payload, { headers: { 'Idempotency-Key': newRequestKey() } })).data,
    onSuccess: refreshCurrent,
  });
  const scanAdd = useMutation({
    mutationFn: async ({ cartId, photoUri, qty }: { cartId: number; photoUri: string; qty: number }) => {
      const form = new FormData();
      form.append('image', { uri: photoUri, name: 'etiqueta.jpg', type: 'image/jpeg' } as unknown as Blob);
      form.append('qty', String(qty));
      return (await api.post<CartEntry>(`/carts/${cartId}/scan?add=1`, form, {
        headers: { 'Content-Type': 'multipart/form-data', 'Idempotency-Key': newRequestKey() },
        transformRequest: (data) => data,
        timeout: SCAN_TIMEOUT_MS,
      })).data;
    },
    onSuccess: refreshCurrent,
  });
  const removeItem = useMutation({
    mutationFn: async ({ cartId, itemId }: { cartId: number; itemId: number }) => (await api.delete<{ cart: Cart }>(`/carts/${cartId}/items/${itemId}`)).data,
    onSuccess: (data, { itemId }) => {
      // Show the reduced total at once instead of waiting for the refetch.
      client.setQueryData<CartDetail | null>(currentCartKey, (cart) => cart && cart.id === data.cart.id ? { ...cart, ...data.cart, items: cart.items.filter((item) => item.id !== itemId) } : cart);
      return refreshCurrent();
    },
  });
  // Corrects the units of a product already added; its unit price stays the same.
  const setQty = useMutation({
    mutationFn: async ({ cartId, itemId, qty }: { cartId: number; itemId: number; qty: number }) =>
      (await api.patch<CartEntry>(`/carts/${cartId}/items/${itemId}`, { qty })).data,
    onSuccess: (data) => {
      client.setQueryData<CartDetail | null>(currentCartKey, (cart) => cart && cart.id === data.cart.id ? { ...cart, ...data.cart, items: cart.items.map((item) => item.id === data.item.id ? data.item : item) } : cart);
      return refreshCurrent();
    },
  });
  // Mobile only keeps the purchase: it never creates a finance movement.
  const finalize = useMutation({
    mutationFn: async (cartId: number) => (await api.post<CartDetail>(`/carts/${cartId}/finalize`, { register_movement: false })).data,
    onSuccess: async () => {
      setCurrent(null);
      await client.invalidateQueries({ queryKey: ['carts'] });
    },
  });
  // Cancelling deletes the cart and its products; nothing is kept in the history.
  const discard = useMutation({
    mutationFn: async (cartId: number) => (await api.delete(`/carts/${cartId}`)).data,
    onSuccess: async () => {
      setCurrent(null);
      await client.invalidateQueries({ queryKey: ['carts'] });
    },
  });
  return { start, addItem, scanAdd, setQty, removeItem, finalize, discard };
}

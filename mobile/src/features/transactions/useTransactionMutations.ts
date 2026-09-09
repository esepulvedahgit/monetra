import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';

type TransactionPayload = { type: 'income' | 'expense'; amount: number; date: string; description: string; category_id: number | null };

export function useTransactionMutations() {
  const client = useQueryClient();
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ['summary'] }), client.invalidateQueries({ queryKey: ['transactions'] })]); };
  const create = useMutation({ mutationFn: async (payload: TransactionPayload) => (await api.post('/transactions', payload, { headers: { 'Idempotency-Key': `${Date.now()}-${Math.random()}` } })).data, onSuccess: refresh });
  const update = useMutation({ mutationFn: async ({ id, payload }: { id: number; payload: TransactionPayload }) => (await api.put(`/transactions/${id}`, payload)).data, onSuccess: refresh });
  const remove = useMutation({ mutationFn: async (id: number) => (await api.delete(`/transactions/${id}`)).data, onSuccess: refresh });
  return { create, update, remove };
}

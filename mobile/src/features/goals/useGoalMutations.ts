import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';

type GoalPayload = { name: string; target_amount: number; current_amount: number; target_date: string | null };

export function useGoalMutations() {
  const client = useQueryClient();
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ['goals'] }), client.invalidateQueries({ queryKey: ['summary'] })]); };
  const create = useMutation({ mutationFn: async (payload: GoalPayload) => (await api.post('/savings', payload)).data, onSuccess: refresh });
  const update = useMutation({ mutationFn: async ({ id, payload }: { id: number; payload: GoalPayload }) => (await api.put(`/savings/${id}`, payload)).data, onSuccess: refresh });
  const contribute = useMutation({ mutationFn: async ({ id, amount }: { id: number; amount: number }) => (await api.post(`/savings/${id}/contribute`, { amount })).data, onSuccess: refresh });
  const remove = useMutation({ mutationFn: async (id: number) => (await api.delete(`/savings/${id}`)).data, onSuccess: refresh });
  return { create, update, contribute, remove };
}

type ClearableQueryClient = {
  cancelQueries: () => Promise<unknown>;
  clear: () => void;
};

export async function clearSessionData(queryClient: ClearableQueryClient, clearPersistentReadCache: () => Promise<void>): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
  await clearPersistentReadCache();
}

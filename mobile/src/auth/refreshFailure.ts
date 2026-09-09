type HttpFailure = { response?: { status?: number } };

export function shouldEndSessionAfterRefreshFailure(error: unknown): boolean {
  const status = (error as HttpFailure).response?.status;
  return status === 401 || status === 403;
}

type StatusCheckError = { response?: { status?: number } };

/** A server rejection is definitive; connection failures are not. */
export function shouldDiscardQuickAccessAfterStatusCheck(error: unknown): boolean {
  const status = (error as StatusCheckError).response?.status;
  return status === 401 || status === 403;
}

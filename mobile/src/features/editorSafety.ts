export function isCurrentEditorSubmission(submissionSession: number, currentSession: number, visible: boolean): boolean {
  return visible && submissionSession === currentSession;
}

export function shouldKeepEditorMounted(visible: boolean, pending: boolean): boolean {
  return visible || pending;
}

export function localDateString(date = new Date(), localUtcOffsetMinutes = -date.getTimezoneOffset()): string {
  const localTime = new Date(date.getTime() + localUtcOffsetMinutes * 60_000);
  const year = localTime.getUTCFullYear();
  const month = String(localTime.getUTCMonth() + 1).padStart(2, '0');
  const day = String(localTime.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

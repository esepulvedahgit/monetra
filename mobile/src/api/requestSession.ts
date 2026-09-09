export type ApiSessionBinding = { generation: number; accountId: number | null };

export class ApiSession {
  private current: ApiSessionBinding = { generation: 0, accountId: null };

  begin(accountId: number | null): ApiSessionBinding {
    this.current = { generation: this.current.generation + 1, accountId };
    return this.current;
  }

  capture(session = this.current): ApiSessionBinding {
    return { ...session };
  }

  isCurrent(session: ApiSessionBinding): boolean {
    return session.generation === this.current.generation;
  }

  canRetry(session: ApiSessionBinding): boolean {
    return this.isCurrent(session);
  }
}

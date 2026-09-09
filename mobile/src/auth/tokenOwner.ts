type TokenPersistence<T> = {
  get: () => Promise<T | null>;
  set: (value: T) => Promise<void>;
  clear: () => Promise<void>;
};

export class SessionTokenOwner<T> {
  private generation = 0;
  private queue: Promise<void> = Promise.resolve();

  constructor(private readonly persistence: TokenPersistence<T>) {}

  begin(): number {
    this.generation += 1;
    return this.generation;
  }

  current(): number {
    return this.generation;
  }

  isCurrent(session: number): boolean {
    return session === this.generation;
  }

  async get(): Promise<T | null> {
    return this.persistence.get();
  }

  set(session: number, value: T): Promise<boolean> {
    return this.enqueue(async () => {
      if (!this.isCurrent(session)) return false;
      await this.persistence.set(value);
      return this.isCurrent(session);
    });
  }

  clear(session: number): Promise<boolean> {
    return this.enqueue(async () => {
      if (!this.isCurrent(session)) return false;
      await this.persistence.clear();
      return this.isCurrent(session);
    });
  }

  private enqueue(task: () => Promise<boolean>): Promise<boolean> {
    const result = this.queue.then(task, task);
    this.queue = result.then(() => undefined, () => undefined);
    return result;
  }
}

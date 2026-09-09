import type { Category, Transaction } from '../../api/types';

export type TransactionDateGroup = { date: string; transactions: Transaction[] };

export function groupTransactionsByDate(transactions: Transaction[]): TransactionDateGroup[] {
  const groups = new Map<string, Transaction[]>();
  transactions.forEach((transaction) => {
    const current = groups.get(transaction.date) ?? [];
    current.push(transaction);
    groups.set(transaction.date, current);
  });
  return Array.from(groups, ([date, grouped]) => ({ date, transactions: grouped }));
}

export function compactFilterLabel(category: Category | null): string | null {
  return category?.name ?? null;
}

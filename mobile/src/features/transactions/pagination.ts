import type { Transaction } from '../../api/types';

export type TransactionPage = { transactions: Transaction[]; total: number; has_next: boolean };

export function flattenTransactionPages(pages: TransactionPage[] | undefined): Transaction[] {
  return pages?.flatMap((page) => page.transactions) ?? [];
}

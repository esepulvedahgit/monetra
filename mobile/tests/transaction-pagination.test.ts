import { describe, expect, it } from 'vitest';

import type { Transaction } from '../src/api/types';
import { flattenTransactionPages } from '../src/features/transactions/pagination';

const transaction = (id: number, type: Transaction['type']): Transaction => ({ id, type, amount: id * 10, date: '2026-09-08' });

describe('flattenTransactionPages', () => {
  it('keeps later pages available to local type and category filters', () => {
    const all = flattenTransactionPages([
      { transactions: [transaction(1, 'income')], total: 101, has_next: true },
      { transactions: [{ ...transaction(101, 'expense'), category_id: 9 }], total: 101, has_next: false },
    ]);

    expect(all.map((item) => item.id)).toEqual([1, 101]);
    expect(all.filter((item) => item.type === 'expense' && item.category_id === 9).map((item) => item.id)).toEqual([101]);
  });
});

import { describe, expect, it } from 'vitest';

import { compactFilterLabel, groupTransactionsByDate } from '../src/features/transactions/presentation';

describe('transaction filters presentation', () => {
  it('groups movements by their date while preserving descending list order', () => {
    const grouped = groupTransactionsByDate([
      { id: 3, type: 'expense', amount: 500, date: '2026-09-12' },
      { id: 2, type: 'income', amount: 800, date: '2026-09-11' },
      { id: 1, type: 'expense', amount: 200, date: '2026-09-11' },
    ]);

    expect(grouped.map((group) => [group.date, group.transactions.map((transaction) => transaction.id)])).toEqual([
      ['2026-09-12', [3]],
      ['2026-09-11', [2, 1]],
    ]);
  });

  it('only shows a compact category label when a category filter is active', () => {
    expect(compactFilterLabel(null)).toBeNull();
    expect(compactFilterLabel({ id: 7, name: 'Alimentación', type: 'expense', color: '#dd5b00', is_global: true })).toBe('Alimentación');
  });
});

import { describe, expect, it } from 'vitest';

import {
  buildGoalPayload,
  buildContributionPayload,
  buildTransactionPayload,
  categoriesForType,
  categorySegments,
  periodFromRouteParams,
  shiftMonth,
  transactionPeriodParams,
  transactionsRouteParams,
} from '../src/finance/presentation';

describe('buildTransactionPayload', () => {
  it('normalizes the form values to the transaction API contract', () => {
    expect(buildTransactionPayload({
      type: 'expense', amount: '12500.50', date: '2026-09-08',
      description: '  Supermercado  ', categoryId: '7',
    })).toEqual({
      type: 'expense', amount: 12500.5, date: '2026-09-08',
      description: 'Supermercado', category_id: 7,
    });
  });

  it('omits an empty category instead of sending an invalid id', () => {
    expect(buildTransactionPayload({
      type: 'income', amount: '500', date: '2026-09-08', description: '', categoryId: '',
    })).toEqual({ type: 'income', amount: 500, date: '2026-09-08', description: '', category_id: null });
  });
});

describe('categorySegments', () => {
  it('keeps the known category shares and leaves the remainder as track', () => {
    expect(categorySegments([
      { id: 1, name: 'Hogar', color: '#0075de', amount: 400, percentage: 40 },
      { id: 2, name: 'Comida', color: '#2a9d99', amount: 350, percentage: 35 },
    ])).toEqual([
      { id: 1, percent: 40, offset: 0 },
      { id: 2, percent: 35, offset: 40 },
    ]);
  });
});

describe('categoriesForType', () => {
  it('does not offer income categories while recording an expense', () => {
    expect(categoriesForType([
      { id: 1, name: 'Sueldo', type: 'income', color: '#1aae39', is_global: true },
      { id: 2, name: 'Comida', type: 'expense', color: '#dd5b00', is_global: true },
    ], 'expense')).toEqual([
      { id: 2, name: 'Comida', type: 'expense', color: '#dd5b00', is_global: true },
    ]);
  });
});

describe('shiftMonth', () => {
  it('crosses a year boundary when moving back from January', () => {
    expect(shiftMonth({ year: 2026, month: 1 }, -1)).toEqual({ year: 2025, month: 12 });
  });
});

describe('transaction period navigation', () => {
  it('passes the selected summary month to the movements route and API query', () => {
    const period = { year: 2026, month: 8 };

    expect(transactionsRouteParams(period)).toEqual({ year: '2026', month: '8' });
    expect(transactionPeriodParams(period)).toEqual({ year: 2026, month: 8 });
  });

  it('falls back to the current month when a direct movement route has invalid period parameters', () => {
    expect(periodFromRouteParams({ year: '2026', month: '0' }, new Date(2026, 8, 8))).toEqual({ year: 2026, month: 9 });
  });
});

describe('buildGoalPayload', () => {
  it('normalizes optional dates and initial savings for the savings API', () => {
    expect(buildGoalPayload({ name: ' Viaje ', targetAmount: '900000', currentAmount: '150000', targetDate: '' })).toEqual({
      name: 'Viaje', target_amount: 900000, current_amount: 150000, target_date: null,
    });
  });
});

describe('buildContributionPayload', () => {
  it('rejects no value in the UI contract and sends a numeric positive amount', () => {
    expect(buildContributionPayload('24500')).toEqual({ amount: 24500 });
  });
});

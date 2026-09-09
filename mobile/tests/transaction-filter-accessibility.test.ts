import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const transactionsScreen = readFileSync('app/(tabs)/transactions.tsx', 'utf8');
const filterSheet = readFileSync('src/features/transactions/TransactionFilterSheet.tsx', 'utf8');

describe('transaction filter accessibility', () => {
  it('exposes selected state for the exclusive type filters', () => {
    expect(transactionsScreen).toContain('accessibilityRole="radio"');
    expect(transactionsScreen).toContain('accessibilityState={{ selected: type === value }}');
    expect(transactionsScreen).toContain('minHeight: 44');
  });

  it('exposes selected state for category options in the filter sheet', () => {
    expect(filterSheet).toContain('accessibilityState={{ selected: selectedCategoryId === null }}');
    expect(filterSheet).toContain('accessibilityState={{ selected: selectedCategoryId === category.id }}');
  });
});

import type { Category, ExpenseCategory, GoalFormValues, TransactionFormValues } from '../api/types';

export type Period = { year: number; month: number };

export function shiftMonth(period: Period, direction: -1 | 1): Period {
  const next = period.month + direction;
  if (next === 0) return { year: period.year - 1, month: 12 };
  if (next === 13) return { year: period.year + 1, month: 1 };
  return { year: period.year, month: next };
}

export function transactionsRouteParams(period: Period) {
  return { year: String(period.year), month: String(period.month) };
}

export function transactionPeriodParams(period: Period) {
  return { year: period.year, month: period.month };
}

export function periodFromRouteParams(
  params: { year?: string | string[]; month?: string | string[] },
  now = new Date(),
): Period {
  const year = Number(Array.isArray(params.year) ? params.year[0] : params.year);
  const month = Number(Array.isArray(params.month) ? params.month[0] : params.month);
  if (Number.isInteger(year) && Number.isInteger(month) && month >= 1 && month <= 12) return { year, month };
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export function buildTransactionPayload(values: TransactionFormValues) {
  const category = values.categoryId.trim();
  return {
    type: values.type,
    amount: Number(values.amount),
    date: values.date,
    description: values.description.trim(),
    category_id: category ? Number(category) : null,
  };
}

export function buildGoalPayload(values: GoalFormValues) {
  return {
    name: values.name.trim(),
    target_amount: Number(values.targetAmount),
    current_amount: Number(values.currentAmount || 0),
    target_date: values.targetDate || null,
  };
}

export function buildContributionPayload(amount: string) {
  return { amount: Number(amount) };
}

export function categorySegments(categories: ExpenseCategory[]) {
  let offset = 0;
  return categories.map((category) => {
    const percent = Math.max(0, Math.min(category.percentage, 100 - offset));
    const segment = { id: category.id, percent, offset };
    offset += percent;
    return segment;
  });
}

export function categoriesForType(categories: Category[], type: TransactionFormValues['type']) {
  return categories.filter((category) => category.type === type);
}

export type User = { id: number; name: string; email: string; country?: string; currency_symbol: string; currency_code: string; language: 'es' | 'en'; mfa_enabled: boolean };
export type Transaction = { id: number; type: 'income' | 'expense'; amount: number; description?: string; date: string; category_id?: number | null; category_name?: string };
export type Goal = { id: number; name: string; target_amount: number; current_amount: number; progress_pct: number; remaining: number; target_date?: string | null; is_completed: boolean };
export type Summary = { total_income: number; total_expense: number; balance: number; budget: { limit: number; spent: number; remaining: number; used_pct: number | null; days_remaining: number }; recent_transactions: Transaction[]; expense_categories: { id: number; name: string; color: string; amount: number; percentage: number }[] };
export type Category = { id: number; name: string; type: 'income' | 'expense'; color: string; is_global: boolean };
export type ExpenseCategory = Summary['expense_categories'][number];
export type TransactionFormValues = { type: 'income' | 'expense'; amount: string; date: string; description: string; categoryId: string };
export type GoalFormValues = { name: string; targetAmount: string; currentAmount: string; targetDate: string };

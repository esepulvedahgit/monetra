import 'transaction.dart';

class CategoryTotal {
  final String name;
  final double total;

  const CategoryTotal({required this.name, required this.total});

  factory CategoryTotal.fromJson(Map<String, dynamic> json) => CategoryTotal(
        name: json['name'],
        total: (json['total'] as num).toDouble(),
      );
}

class DashboardSummary {
  final int year;
  final int month;
  final double totalIncome;
  final double totalExpense;
  final double balance;
  final double budgetAmount;
  final double? budgetUsedPct;
  final List<CategoryTotal> topExpenseCategories;
  final List<Transaction> recentTransactions;

  const DashboardSummary({
    required this.year,
    required this.month,
    required this.totalIncome,
    required this.totalExpense,
    required this.balance,
    required this.budgetAmount,
    this.budgetUsedPct,
    required this.topExpenseCategories,
    required this.recentTransactions,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) =>
      DashboardSummary(
        year: json['year'],
        month: json['month'],
        totalIncome: (json['total_income'] as num).toDouble(),
        totalExpense: (json['total_expense'] as num).toDouble(),
        balance: (json['balance'] as num).toDouble(),
        budgetAmount: (json['budget_amount'] as num).toDouble(),
        budgetUsedPct: json['budget_used_pct'] != null
            ? (json['budget_used_pct'] as num).toDouble()
            : null,
        topExpenseCategories: (json['top_expense_categories'] as List)
            .map((e) => CategoryTotal.fromJson(e))
            .toList(),
        recentTransactions: (json['recent_transactions'] as List)
            .map((e) => Transaction.fromJson(e))
            .toList(),
      );
}

class YearlySummary {
  final int year;
  final double income;
  final double expense;

  const YearlySummary({
    required this.year,
    required this.income,
    required this.expense,
  });

  factory YearlySummary.fromJson(Map<String, dynamic> json) => YearlySummary(
        year: json['year'],
        income: (json['income'] as num).toDouble(),
        expense: (json['expense'] as num).toDouble(),
      );
}

class DashboardGlobal {
  final int year;
  final int fromMonth;
  final int toMonth;
  final List<double> trendIncome;
  final List<double> trendExpense;
  final List<CategoryTotal> expenseByCategory;
  final List<YearlySummary> yearlySummary;

  const DashboardGlobal({
    required this.year,
    required this.fromMonth,
    required this.toMonth,
    required this.trendIncome,
    required this.trendExpense,
    required this.expenseByCategory,
    required this.yearlySummary,
  });

  factory DashboardGlobal.fromJson(Map<String, dynamic> json) =>
      DashboardGlobal(
        year: json['year'],
        fromMonth: json['from_month'],
        toMonth: json['to_month'],
        trendIncome: (json['trend_income'] as List)
            .map((e) => (e as num).toDouble())
            .toList(),
        trendExpense: (json['trend_expense'] as List)
            .map((e) => (e as num).toDouble())
            .toList(),
        expenseByCategory: (json['expense_by_category'] as List)
            .map((e) => CategoryTotal.fromJson(e))
            .toList(),
        yearlySummary: (json['yearly_summary'] as List)
            .map((e) => YearlySummary.fromJson(e))
            .toList(),
      );
}

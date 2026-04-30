class Transaction {
  final int id;
  final String type; // 'income' | 'expense'
  final double amount;
  final String? description;
  final String date; // ISO 8601: YYYY-MM-DD
  final int? categoryId;
  final String? categoryName;
  final bool isDemo;
  final String? createdAt;

  const Transaction({
    required this.id,
    required this.type,
    required this.amount,
    this.description,
    required this.date,
    this.categoryId,
    this.categoryName,
    required this.isDemo,
    this.createdAt,
  });

  bool get isExpense => type == 'expense';
  bool get isIncome => type == 'income';

  factory Transaction.fromJson(Map<String, dynamic> json) => Transaction(
        id: json['id'],
        type: json['type'],
        amount: (json['amount'] as num).toDouble(),
        description: json['description'],
        date: json['date'],
        categoryId: json['category_id'],
        categoryName: json['category_name'],
        isDemo: json['is_demo'] ?? false,
        createdAt: json['created_at'],
      );

  Map<String, dynamic> toJson() => {
        'type': type,
        'amount': amount,
        'description': description,
        'date': date,
        'category_id': categoryId,
      };
}

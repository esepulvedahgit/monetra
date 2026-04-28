class Budget {
  final int id;
  final int year;
  final int month;
  final double amount;

  const Budget({
    required this.id,
    required this.year,
    required this.month,
    required this.amount,
  });

  factory Budget.fromJson(Map<String, dynamic> json) => Budget(
        id: json['id'],
        year: json['year'],
        month: json['month'],
        amount: (json['amount'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'year': year,
        'month': month,
        'amount': amount,
      };
}

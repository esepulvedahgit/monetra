class Category {
  final int id;
  final String name;
  final String type; // 'income' | 'expense'
  final bool isGlobal;

  const Category({
    required this.id,
    required this.name,
    required this.type,
    required this.isGlobal,
  });

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'],
        name: json['name'],
        type: json['type'],
        isGlobal: json['is_global'] ?? false,
      );
}

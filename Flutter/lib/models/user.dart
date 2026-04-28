class User {
  final int id;
  final String username;
  final String email;
  final String? country;
  final String currencySymbol;
  final String currencyCode;
  final String currencyLocale;
  final String language;
  final String role;
  final String? createdAt;

  const User({
    required this.id,
    required this.username,
    required this.email,
    this.country,
    required this.currencySymbol,
    required this.currencyCode,
    required this.currencyLocale,
    required this.language,
    required this.role,
    this.createdAt,
  });

  bool get isAdmin => role == 'admin';

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'],
        username: json['username'],
        email: json['email'],
        country: json['country'],
        currencySymbol: json['currency_symbol'] ?? '\$',
        currencyCode: json['currency_code'] ?? 'USD',
        currencyLocale: json['currency_locale'] ?? 'es',
        language: json['language'] ?? 'es',
        role: json['role'] ?? 'user',
        createdAt: json['created_at'],
      );
}

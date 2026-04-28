import '../models/budget.dart';
import 'api_client.dart';

class BudgetService {
  static Future<List<Budget>> list({int? year}) async {
    final params = <String, String>{
      if (year != null) 'year': '$year',
    };
    final data = await ApiClient.get('/budgets', params: params);
    return (data as List).map((e) => Budget.fromJson(e)).toList();
  }

  static Future<Budget> upsert(int year, int month, double amount) async {
    final data = await ApiClient.post('/budgets', body: {
      'year': year,
      'month': month,
      'amount': amount,
    });
    return Budget.fromJson(data);
  }

  static Future<Budget> update(int id, double amount) async {
    final data = await ApiClient.put('/budgets/$id', body: {'amount': amount});
    return Budget.fromJson(data);
  }
}

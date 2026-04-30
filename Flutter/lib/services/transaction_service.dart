import '../models/transaction.dart';
import 'api_client.dart';

class TransactionService {
  static Future<({List<Transaction> transactions, int total})> list({
    int? year,
    int? month,
    String? type,
    int? categoryId,
  }) async {
    final params = <String, String>{
      if (year != null) 'year': '$year',
      if (month != null) 'month': '$month',
      if (type != null) 'type': type,
      if (categoryId != null) 'category_id': '$categoryId',
    };
    final data = await ApiClient.get('/transactions', params: params);
    final txs = (data['transactions'] as List)
        .map((e) => Transaction.fromJson(e))
        .toList();
    return (transactions: txs, total: data['total'] as int);
  }

  static Future<Transaction> create(Transaction tx) async {
    final data = await ApiClient.post('/transactions', body: tx.toJson());
    return Transaction.fromJson(data);
  }

  static Future<Transaction> update(int id, Map<String, dynamic> fields) async {
    final data = await ApiClient.put('/transactions/$id', body: fields);
    return Transaction.fromJson(data);
  }

  static Future<void> delete(int id) async {
    await ApiClient.delete('/transactions/$id');
  }
}

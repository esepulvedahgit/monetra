import '../models/category.dart';
import 'api_client.dart';

class CategoryService {
  static Future<List<Category>> list({String? type}) async {
    final params = <String, String>{
      if (type != null) 'type': type,
    };
    final data = await ApiClient.get('/categories', params: params);
    return (data as List).map((e) => Category.fromJson(e)).toList();
  }
}

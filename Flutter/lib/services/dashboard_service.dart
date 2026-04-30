import '../models/dashboard.dart';
import 'api_client.dart';

class DashboardService {
  static Future<DashboardSummary> summary({
    required int year,
    required int month,
  }) async {
    final data = await ApiClient.get('/dashboard/summary', params: {
      'year': '$year',
      'month': '$month',
    });
    return DashboardSummary.fromJson(data);
  }

  static Future<DashboardGlobal> global({
    required int year,
    int fromMonth = 1,
    int toMonth = 12,
  }) async {
    final data = await ApiClient.get('/dashboard/global', params: {
      'year': '$year',
      'from_month': '$fromMonth',
      'to_month': '$toMonth',
    });
    return DashboardGlobal.fromJson(data);
  }
}

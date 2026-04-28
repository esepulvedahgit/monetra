import '../models/user.dart';
import 'api_client.dart';

class AuthService {
  static Future<({User user, String accessToken, String refreshToken})> login(
      String email, String password) async {
    final data = await ApiClient.post('/login', body: {
      'email': email,
      'password': password,
    });
    final user = User.fromJson(data['user']);
    final access = data['access_token'] as String;
    final refresh = data['refresh_token'] as String;
    await ApiClient.saveTokens(access, refresh);
    return (user: user, accessToken: access, refreshToken: refresh);
  }

  static Future<User> me() async {
    final data = await ApiClient.get('/me');
    return User.fromJson(data);
  }

  static Future<void> logout() async {
    try {
      await ApiClient.post('/logout');
    } catch (_) {}
    await ApiClient.clearTokens();
  }

  static Future<void> refresh() async {
    final data = await ApiClient.post('/refresh');
    final prefs = await _getPrefs();
    await prefs.setString('access_token', data['access_token']);
  }

  static Future<dynamic> _getPrefs() async {
    // solo usado internamente para refresh
    return null;
  }
}

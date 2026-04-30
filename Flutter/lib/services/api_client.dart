import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/api_config.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  static const _keyAccessToken = 'access_token';
  static const _keyRefreshToken = 'refresh_token';

  // ── Token storage ─────────────────────────────────────

  static Future<String?> getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyAccessToken);
  }

  static Future<void> saveTokens(String access, String refresh) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyAccessToken, access);
    await prefs.setString(_keyRefreshToken, refresh);
  }

  static Future<void> clearTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyAccessToken);
    await prefs.remove(_keyRefreshToken);
  }

  static Future<bool> hasToken() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  // ── Headers ───────────────────────────────────────────

  static Future<Map<String, String>> _authHeaders() async {
    final token = await getAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // ── Peticiones base ───────────────────────────────────

  static Future<dynamic> get(String path, {Map<String, String>? params}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}$path')
        .replace(queryParameters: params);
    final headers = await _authHeaders();
    final response = await http.get(uri, headers: headers);
    return _handle(response);
  }

  static Future<dynamic> post(String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}$path');
    final headers = await _authHeaders();
    final response = await http.post(
      uri,
      headers: headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handle(response);
  }

  static Future<dynamic> put(String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}$path');
    final headers = await _authHeaders();
    final response = await http.put(
      uri,
      headers: headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handle(response);
  }

  static Future<void> delete(String path) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}$path');
    final headers = await _authHeaders();
    final response = await http.delete(uri, headers: headers);
    _handle(response);
  }

  // ── Response handler ──────────────────────────────────

  static dynamic _handle(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(utf8.decode(response.bodyBytes));
    }

    String message = 'Error ${response.statusCode}';
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      message = body['error'] ?? message;
    } catch (_) {}

    throw ApiException(response.statusCode, message);
  }
}

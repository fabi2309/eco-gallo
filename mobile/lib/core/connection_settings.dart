import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

/// Only the server address is persisted. Credentials remain in memory.
class ConnectionSettings {
  final _preferences = SharedPreferencesAsync();
  static const key = 'ecogallo.server_url';

  Future<String?> load() async {
    try {
      final value = await _preferences.getString(key);
      return value == null ? null : ApiClient.serverUri(value).origin;
    } on ApiException {
      return null;
    } on PlatformException {
      return null;
    }
  }

  Future<void> save(String value) async {
    final url = ApiClient.serverUri(value).origin;
    try {
      await _preferences.setString(key, url);
    } on PlatformException {
      throw const ApiException(
        'No pudimos guardar la dirección. Intenta nuevamente.',
      );
    }
  }
}

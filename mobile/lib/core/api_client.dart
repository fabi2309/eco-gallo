import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, {this.status = 0, this.data = const {}});
  final String message;
  final int status;
  final Map<String, dynamic> data;
  @override
  String toString() => message;
}

/// One origin and an in-memory session. Never writes passwords or cookies to disk.
class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
    : _http = client ?? http.Client() {
    setBaseUrl(
      baseUrl ??
          const String.fromEnvironment(
            'API_BASE_URL',
            defaultValue: 'http://127.0.0.1:8080',
          ),
    );
  }

  final http.Client _http;
  late Uri baseUri;
  String? _cookie;
  String? _csrf;
  int _epoch = 0;
  int _cookieVersion = 0;
  VoidCallback? onSessionExpired;
  VoidCallback? onInboxChanged;
  String get baseUrl => baseUri.origin;

  void setBaseUrl(String value) {
    baseUri = serverUri(value);
    clearSession();
  }

  static const localNetworkBuild = bool.fromEnvironment('LOCAL_NETWORK_BUILD');

  static bool _privateIpv4(String host) {
    final parts = host.split('.');
    if (parts.length != 4) return false;
    final octets = parts.map(int.tryParse).toList();
    if (octets.any((n) => n == null || n < 0 || n > 255)) return false;
    for (var i = 0; i < 4; i++) {
      if (parts[i] != octets[i].toString()) return false;
    }
    return octets[0] == 10 ||
        (octets[0] == 172 && octets[1]! >= 16 && octets[1]! <= 31) ||
        (octets[0] == 192 && octets[1] == 168);
  }

  static Uri serverUri(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw const ApiException(
        'Usa una dirección como http://127.0.0.1:8080, sin rutas ni contraseñas.',
      );
    }
    final loopback = ['127.0.0.1', 'localhost', '10.0.2.2'].contains(uri.host);
    final localAllowed =
        !kReleaseMode &&
        (loopback || (localNetworkBuild && _privateIpv4(uri.host)));
    if (uri.scheme == 'http' && !localAllowed) {
      throw const ApiException(
        'Usa HTTPS. El APK local de la tesina admite HTTP solo por USB o con una IP privada de la red local.',
      );
    }
    return Uri.parse('${uri.origin}/');
  }

  void clearSession() {
    _epoch++;
    _cookie = null;
    _csrf = null;
  }

  Uri? imageUri(String? path) {
    if (path == null || path.isEmpty) return null;
    try {
      final result = baseUri.resolve(path);
      if (!['http', 'https'].contains(result.scheme)) return null;
      return result.origin == baseUri.origin && result.userInfo.isEmpty
          ? result
          : null;
    } on FormatException {
      return null;
    }
  }

  Future<Map<String, dynamic>> get(String path, [Map<String, String>? query]) =>
      request('GET', path, query: query);
  Future<Map<String, dynamic>> post(
    String path, [
    Map<String, dynamic>? data,
  ]) => request('POST', path, data: data ?? {});
  Future<Map<String, dynamic>> put(String path, Map<String, dynamic> data) =>
      request('PUT', path, data: data);
  Future<Map<String, dynamic>> delete(String path) =>
      request('DELETE', path, data: {});

  Future<Map<String, dynamic>> multipart(
    String method,
    String path,
    Map<String, String> fields,
    List<http.MultipartFile> files,
  ) => request(method, path, formFields: fields, files: files);

  Future<Map<String, dynamic>> request(
    String method,
    String path, {
    Map<String, dynamic>? data,
    Map<String, String>? query,
    Map<String, String>? formFields,
    List<http.MultipartFile> files = const [],
  }) async {
    if (!path.startsWith('/api/')) {
      throw const ApiException('Ruta de API inválida.');
    }
    final requestEpoch = _epoch;
    int? requestCookieVersion;
    void checkSession() {
      if (requestEpoch != _epoch ||
          (requestCookieVersion != null &&
              requestCookieVersion != _cookieVersion)) {
        throw const ApiException(
          'La conexión o la sesión cambió. Intenta nuevamente.',
        );
      }
    }

    if (method != 'GET' && _csrf == null) await get('/api/me');
    checkSession();
    requestCookieVersion = _cookieVersion;
    final headers = <String, String>{'Accept': 'application/json'};
    if (_cookie != null) headers['Cookie'] = _cookie!;
    if (method != 'GET') headers['X-CSRF-Token'] = _csrf ?? '';
    if (data != null) headers['Content-Type'] = 'application/json';
    final uri = baseUri.resolve(path).replace(queryParameters: query);
    try {
      final http.BaseRequest req;
      if (formFields != null) {
        req = http.MultipartRequest(method, uri)
          ..fields.addAll(formFields)
          ..files.addAll(files);
      } else {
        req = http.Request(method, uri);
        if (data != null) (req as http.Request).body = jsonEncode(data);
      }
      req.headers.addAll(headers);
      req.followRedirects = false;
      final response = await (() async => http.Response.fromStream(
        await _http.send(req),
      ))().timeout(Duration(seconds: formFields == null ? 15 : 60));
      checkSession();
      final setCookie = response.headers['set-cookie'];
      if (setCookie != null) {
        final session = RegExp(r'(?:^|,\s*)eg_session=([^;]*)')
            .firstMatch(setCookie);
        if (session != null) {
          final value = session.group(1)!;
          final nextCookie = value.isEmpty ? null : 'eg_session=$value';
          if (nextCookie != _cookie) {
            _cookie = nextCookie;
            _cookieVersion++;
          }
        }
      }
      if (response.statusCode == 401 && !path.startsWith('/api/auth/')) {
        clearSession();
        onSessionExpired?.call();
      }
      Map<String, dynamic> body;
      try {
        final decoded = jsonDecode(utf8.decode(response.bodyBytes));
        if (decoded is! Map<String, dynamic>) throw const FormatException();
        body = decoded;
      } on FormatException {
        throw ApiException(
          'El servidor no devolvió una respuesta válida. Revisa la dirección de conexión.',
          status: response.statusCode,
        );
      }
      if (body['csrf_token'] is String) _csrf = body['csrf_token'] as String;
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          body['message'] as String? ?? 'No se pudo completar la solicitud.',
          status: response.statusCode,
          data: body,
        );
      }
      if (path == '/api/messages' || path == '/api/notifications/read') {
        onInboxChanged?.call();
      }
      return body;
    } on TimeoutException {
      throw ApiException(
        formFields == null
            ? 'El servidor tardó demasiado. Comprueba que el backend esté encendido e intenta de nuevo.'
            : 'No pudimos confirmar el envío. Revisa Mis publicaciones antes de intentarlo otra vez para evitar duplicados.',
      );
    } on http.ClientException {
      throw ApiException(
        formFields == null
            ? 'No pudimos conectar. Enciende el backend y revisa la conexión USB o del emulador.'
            : 'Se interrumpió la conexión durante el envío. Revisa Mis publicaciones antes de volver a enviarlo.',
      );
    }
  }

  Future<void> logout() async {
    try {
      await post('/api/auth/logout');
    } finally {
      clearSession();
    }
  }

  void close() {
    onInboxChanged = null;
    clearSession();
    _http.close();
  }
}

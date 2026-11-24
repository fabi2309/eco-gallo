import 'package:flutter/foundation.dart';

import '../models/models.dart';
import 'api_client.dart';

enum SessionPhase {
  loading,
  offline,
  signedOut,
  profile,
  pending,
  terms,
  signedIn,
}

class SessionController extends ChangeNotifier {
  SessionController(this.api, {this.saveServer}) {
    api.onSessionExpired = () {
      if (_disposed || _loggingOut) return;
      _generation++;
      user = null;
      challenge = null;
      busy = false;
      unreadMessages = 0;
      unreadNotifications = 0;
      phase = SessionPhase.signedOut;
      error = 'Tu sesión venció. Inicia sesión nuevamente.';
      _emit();
    };
  }
  final ApiClient api;
  final Future<void> Function(String)? saveServer;
  SessionPhase phase = SessionPhase.loading;
  Student? user;
  Map<String, dynamic> meta = {};
  bool busy = false;
  String? error;
  String? challenge;
  String verificationMessage = '';
  int unreadMessages = 0, unreadNotifications = 0;
  int _generation = 0, _sessionRead = 0;
  bool _disposed = false, _loggingOut = false;
  bool _current(int generation) => !_disposed && generation == _generation;
  void _emit() {
    if (!_disposed) notifyListeners();
  }

  List<String> get categories =>
      List<String>.from(meta['categories'] as List? ?? []);
  List<String> get carreras => (meta['carreras'] as Map<String, dynamic>? ?? {})
      .values
      .expand((list) => List<String>.from(list as List))
      .toList();
  String get paymentMode => meta['payment_mode'] as String? ?? 'disabled';

  Future<void> initialize() async {
    if (_disposed || _loggingOut) return;
    final generation = ++_generation;
    phase = SessionPhase.loading;
    user = null;
    challenge = null;
    busy = false;
    unreadMessages = 0;
    unreadNotifications = 0;
    error = null;
    _emit();
    try {
      await api.get('/api/health');
      if (!_current(generation)) return;
      final result = await api.get('/api/meta');
      if (!_current(generation)) return;
      meta = result;
      await refreshSession(expectedGeneration: generation);
    } on ApiException catch (e) {
      if (!_current(generation)) return;
      error = e.message;
      phase = SessionPhase.offline;
    } finally {
      if (_current(generation)) _emit();
    }
  }

  Future<void> refreshSession({int? expectedGeneration}) async {
    if (_disposed || _loggingOut) return;
    final generation = expectedGeneration ?? _generation;
    final read = ++_sessionRead;
    final data = await api.get('/api/me');
    if (!_current(generation) || read != _sessionRead) return;
    final raw = data['user'];
    user = raw == null ? null : Student.fromJson(raw as Map<String, dynamic>);
    phase = user == null
        ? SessionPhase.signedOut
        : data['needs_profile'] == true
        ? SessionPhase.profile
        : data['needs_verification'] == true
        ? SessionPhase.pending
        : data['needs_terms'] == true
        ? SessionPhase.terms
        : SessionPhase.signedIn;
    final verification = data['verification'] as Map<String, dynamic>?;
    verificationMessage = verification?['note'] as String? ?? '';
    unreadMessages = data['unread_messages'] as int? ?? 0;
    unreadNotifications = data['unread_notifications'] as int? ?? 0;
    _emit();
  }

  Future<Map<String, dynamic>?> action(
    Future<Map<String, dynamic>> Function() run, {
    bool authenticate = false,
  }) async {
    if (busy || _disposed || _loggingOut) return null;
    final generation = _generation;
    busy = true;
    error = null;
    _emit();
    try {
      final result = await run();
      if (!_current(generation)) return null;
      if (authenticate) {
        if (result['needs_totp'] == true) {
          challenge = result['challenge_token'] as String;
        } else {
          challenge = null;
          await refreshSession();
        }
      }
      return result;
    } on ApiException catch (e) {
      if (!_current(generation)) return null;
      error = e.message;
      return null;
    } finally {
      if (_current(generation)) {
        busy = false;
        _emit();
      }
    }
  }

  Future<void> login(String email, String password) async {
    await action(
      () => api.post('/api/auth/login', {
        'email': email.trim().toLowerCase(),
        'password': password,
      }),
      authenticate: true,
    );
  }

  Future<void> verifyCode(String email, String code) async {
    await action(
      () => api.post('/api/auth/verify', {
        'email': email.trim().toLowerCase(),
        'code': code.trim(),
      }),
      authenticate: true,
    );
  }

  Future<void> verifyTotp(String code) async {
    await action(
      () => api.post('/api/auth/totp/verify', {
        'challenge_token': challenge,
        'code': code.trim(),
      }),
      authenticate: true,
    );
  }

  Future<void> completeProfile(String name, String carrera) async {
    await action(() async {
      final data = await api.put('/api/me', {
        'name': name.trim(),
        'carrera': carrera,
      });
      await refreshSession();
      return data;
    });
  }

  Future<void> logout() async {
    if (_disposed || _loggingOut) return;
    _loggingOut = true;
    _generation++;
    busy = true;
    error = null;
    user = null;
    challenge = null;
    unreadMessages = 0;
    unreadNotifications = 0;
    phase = SessionPhase.signedOut;
    _emit();
    try {
      await api.logout();
    } on ApiException {
      if (!_disposed) error = 'Cerraste la sesión en este dispositivo. Sin conexión no se pudo confirmar su revocación en el servidor.';
    } finally {
      _loggingOut = false;
      if (!_disposed) {
        busy = false;
        _emit();
      }
    }
  }

  void resetChallenge() {
    challenge = null;
    error = null;
    _emit();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    api.onSessionExpired = null;
    super.dispose();
  }
}

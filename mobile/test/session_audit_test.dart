import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/session_controller.dart';
import 'package:eco_gallo_mobile/models/models.dart';

void main() {
  test('Cerrar sesión sin red elimina la sesión local', () async {
    var requests = 0;
    final api = ApiClient(
      client: MockClient((r) async {
        requests++;
        if (requests == 1) return http.Response('{"csrf_token":"csrf"}', 200);
        if (requests == 2) {
          return http.Response(
            '{"csrf_token":"csrf2"}',
            200,
            headers: {'set-cookie': 'eg_session=private; HttpOnly'},
          );
        }
        if (requests == 3) throw http.ClientException('Sin conexión');
        expect(r.headers.containsKey('Cookie'), false);
        return http.Response('{}', 200);
      }),
    );
    final s = SessionController(api)
      ..phase = SessionPhase.signedIn
      ..user = Student.fromJson({'id': 1, 'name': 'Persona'});
    await api.post('/api/auth/login');
    await s.logout();
    expect(s.phase, SessionPhase.signedOut);
    expect(s.user, isNull);
    await api.get('/api/me');
    s.dispose();
    api.close();
  });
  test('Una petición que termina después de dispose no notifica', () async {
    final pending = Completer<http.Response>();
    final started = Completer<void>();
    final api = ApiClient(
      client: MockClient((r) async {
        if (!started.isCompleted) started.complete();
        return pending.future;
      }),
    );
    final s = SessionController(api);
    final task = s.initialize();
    await started.future;
    s.dispose();
    pending.complete(http.Response('{}', 200));
    await expectLater(task, completes);
    api.close();
  });
}

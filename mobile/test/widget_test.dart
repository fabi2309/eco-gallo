import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';

void main() {
  testWidgets(
    'Sin servidor: permite configurar conexión con teclado sin desbordarse',
    (tester) async {
      tester.view.physicalSize = const Size(720, 1280);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetViewInsets);
      final api = ApiClient(
        client: MockClient((_) async {
          throw http.ClientException('Servidor apagado');
        }),
      );
      await tester.pumpWidget(EcoGalloApp(api: api));
      await tester.pumpAndSettle();
      expect(find.text('Conecta con tu comunidad'), findsOneWidget);
      await tester.tap(find.text('Configurar conexión'));
      await tester.pumpAndSettle();
      tester.view.viewInsets = const FakeViewPadding(bottom: 600);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  test(
    'Descarta una respuesta del servidor anterior al cambiar conexión',
    () async {
      final response = Completer<http.Response>();
      final started = Completer<void>();
      final requests = <http.Request>[];
      final api = ApiClient(
        client: MockClient((request) async {
          requests.add(request);
          if (requests.length == 1) {
            started.complete();
            return response.future;
          }
          return http.Response('{}', 200);
        }),
      );
      final pending = api.get('/api/posts');
      final rejected = expectLater(pending, throwsA(isA<ApiException>()));
      await started.future;
      api.setBaseUrl('https://example.com');
      response.complete(
        http.Response(
          '{}',
          200,
          headers: {'set-cookie': 'eg_session=old; HttpOnly'},
        ),
      );
      await rejected;
      await api.get('/api/posts');
      expect(requests.last.url.host, 'example.com');
      expect(requests.last.headers.containsKey('Cookie'), false);
      api.close();
    },
  );
  test('Conserva cookie, rota CSRF y limpia sesión al salir', () async {
    final seen = <http.Request>[];
    final api = ApiClient(
      client: MockClient((request) async {
        seen.add(request);
        if (request.url.path == '/api/me') {
          return http.Response('{"user":null,"csrf_token":"initial"}', 200);
        }
        if (request.url.path.endsWith('login')) {
          return http.Response(
            '{"csrf_token":"rotated"}',
            200,
            headers: {
              'set-cookie': 'eg_session=opaque; HttpOnly; SameSite=Lax',
            },
          );
        }
        return http.Response('{"ok":true}', 200);
      }),
    );
    await api.post('/api/auth/login', {
      'email': 'test@edu.uaa.mx',
      'password': 'secret',
    });
    expect(seen[1].headers['X-CSRF-Token'], 'initial');
    await api.logout();
    expect(seen[2].headers['Cookie'], 'eg_session=opaque');
    expect(seen[2].headers['X-CSRF-Token'], 'rotated');
    await api.get('/api/posts');
    expect(seen.last.headers.containsKey('Cookie'), false);
    api.close();
  });
  test('Rechaza HTTP externo y descarta imágenes de otro servidor', () {
    final api = ApiClient();
    expect(
      () => api.setBaseUrl('http://example.com'),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => api.setBaseUrl('https://user:password@example.com'),
      throwsA(isA<ApiException>()),
    );
    expect(api.imageUri('//example.com/photo.jpg'), isNull);
    expect(api.imageUri('/uploads/photo.jpg')!.host, '127.0.0.1');
    api.close();
  });
  test('Una sesión vencida limpia la cookie y notifica', () async {
    var expired = false;
    final api = ApiClient(
      client: MockClient(
        (r) async => http.Response('{"message":"Venció"}', 401),
      ),
    );
    api.onSessionExpired = () => expired = true;
    await expectLater(api.get('/api/posts'), throwsA(isA<ApiException>()));
    expect(expired, true);
    api.close();
  });
  testWidgets('Acceso, búsqueda, detalle y cierre de sesión', (tester) async {
    var loggedIn = false;
    String? query;
    final post = {
      'id': 1,
      'title': 'Libro de prueba',
      'description': 'Material en buen estado',
      'category': 'Libros',
      'tipo': 'venta',
      'price_cents': 25000,
      'condition': 'Usado',
      'status': 'active',
      'images': [],
      'author': {'id': 2, 'name': 'Ana'},
    };
    final api = ApiClient(
      client: MockClient((r) async {
        final path = r.url.path;
        Map<String, dynamic> data = {};
        if (path == '/api/health') data = {'ok': true};
        if (path == '/api/meta') {
          data = {
            'categories': ['Libros'],
            'carreras': {},
            'payment_mode': 'demo',
          };
        }
        if (path.endsWith('/login')) loggedIn = true;
        if (path.endsWith('/logout')) loggedIn = false;
        if (path == '/api/me') {
          data = {
            'user': loggedIn ? {'id': 1, 'name': 'Demo'} : null,
            'csrf_token': 'csrf',
          };
        }
        if (path == '/api/posts') {
          query = r.url.queryParameters['q'];
          data = {
            'posts': [post],
            'page': 1,
            'pages': 1,
            'total': 1,
          };
        }
        if (path == '/api/posts/1') data = {'post': post};
        return http.Response(
          jsonEncode(data),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );
    await tester.pumpWidget(EcoGalloApp(api: api));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('email')), 'movil@edu.uaa.mx');
    await tester.enterText(find.byKey(const Key('password')), 'example');
    await tester.ensureVisible(find.byKey(const Key('sign-in')));
    await tester.tap(find.byKey(const Key('sign-in')));
    await tester.pumpAndSettle();
    expect(find.text('Hola, Demo.'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('search')), 'Libro');
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pumpAndSettle();
    expect(query, 'Libro');
    await tester.ensureVisible(find.byKey(const Key('post-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('post-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('detail-title')), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Cerrar sesión'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('email')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

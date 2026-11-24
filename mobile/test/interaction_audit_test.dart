import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/session_controller.dart';
import 'package:eco_gallo_mobile/core/photo_picker_service.dart';
import 'package:eco_gallo_mobile/features/community/community_screens.dart';
import 'package:eco_gallo_mobile/features/community/chat_screen.dart';
import 'package:eco_gallo_mobile/features/orders/orders_screen.dart';
import 'package:eco_gallo_mobile/features/catalog/detail_screen.dart';
import 'package:eco_gallo_mobile/features/posts/post_editor_screen.dart';
import 'package:eco_gallo_mobile/models/models.dart';

import 'mobile_layout_audit_test.dart' as fixtures;

http.Response json(Object value) => http.Response(
  jsonEncode(value),
  200,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

void main() {
  test(
    'Una respuesta anterior al login no reemplaza cookie ni CSRF nuevos',
    () async {
      final late = Completer<http.Response>();
      final started = Completer<void>();
      final seen = <http.Request>[];
      var reads = 0;
      final api = ApiClient(
        client: MockClient((r) async {
          seen.add(r);
          if (r.url.path == '/api/me') {
            if (++reads == 2) {
              started.complete();
              return late.future;
            }
            return json({'csrf_token': 'initial'});
          }
          if (r.url.path.endsWith('/login')) {
            return http.Response(
              '{"csrf_token":"new-csrf"}',
              200,
              headers: {'set-cookie': 'eg_session=new; HttpOnly'},
            );
          }
          return json({});
        }),
      );
      await api.get('/api/me');
      final old = api.get('/api/me');
      final rejected = expectLater(old, throwsA(isA<ApiException>()));
      await started.future;
      await api.post('/api/auth/login');
      late.complete(
        http.Response(
          '{"csrf_token":"stale"}',
          200,
          headers: {'set-cookie': 'eg_session=old; HttpOnly'},
        ),
      );
      await rejected;
      await api.post('/api/messages');
      expect(seen.last.headers['Cookie'], 'eg_session=new');
      expect(seen.last.headers['X-CSRF-Token'], 'new-csrf');
      api.close();
    },
  );

  test('Imágenes inválidas o con credenciales no provocan errores', () {
    final api = ApiClient();
    for (final path in [
      'data:image/png;base64,AAA',
      'javascript:void(0)',
      'file:///private/photo',
      'http://user:password@127.0.0.1:8080/a',
      'http://[invalid',
      'https://external.example/a',
    ]) {
      expect(api.imageUri(path), isNull, reason: path);
    }
    api.close();
  });

  testWidgets('Dos toques de pedido abren una sola confirmación', (
    tester,
  ) async {
    final api = fixtures.testApi();
    await tester.pumpWidget(MaterialApp(home: OrderDetailScreen(api, 1)));
    await tester.pumpAndSettle();
    final button = find.byKey(const Key('order-action-confirm'));
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    final callback = tester.widget<FilledButton>(button).onPressed!;
    callback();
    callback();
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    api.close();
  });

  testWidgets('Dos toques en Contactar abren una sola conversación', (
    tester,
  ) async {
    final api = fixtures.testApi();
    await tester.pumpWidget(MaterialApp(home: DetailScreen(api, 2)));
    await tester.pumpAndSettle();
    final button = find.byKey(const Key('contact-author'));
    await tester.scrollUntilVisible(button, 200);
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    final callback = tester.widget<FilledButton>(button).onPressed!;
    callback();
    callback();
    await tester.pumpAndSettle();
    expect(find.byType(ChatScreen, skipOffstage: false), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    api.close();
  });

  testWidgets('Rotar conserva el borrador', (tester) async {
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = fixtures.testApi();
    final session = SessionController(api)
      ..meta = Map<String, dynamic>.from(fixtures.meta)
      ..phase = SessionPhase.signedIn
      ..user = Student.fromJson(Map<String, dynamic>.from(fixtures.user));
    tester.view.physicalSize = const Size(360, 640);
    await tester.pumpWidget(
      MaterialApp(home: PostEditorScreen(session, PhotoPickerService())),
    );
    await tester.pumpAndSettle();
    final title = find.byKey(const Key('post-title'));
    await tester.enterText(title, 'Borrador que se conserva');
    tester.view.physicalSize = const Size(640, 360);
    await tester.pumpAndSettle();
    expect(
      tester.widget<TextFormField>(title).controller!.text,
      'Borrador que se conserva',
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
    api.close();
  });

  testWidgets('Notificaciones: solo lee la pulsada y se actualiza al volver', (
    tester,
  ) async {
    var reads = 0;
    final marked = <int>[];
    final api = ApiClient(
      client: MockClient((r) async {
        if (r.url.path == '/api/me') return json({'csrf_token': 'csrf'});
        if (r.url.path.endsWith('/read')) {
          marked.addAll(List<int>.from(jsonDecode(r.body)['ids']));
          return json({});
        }
        reads++;
        return json({
          'notifications': [
            for (var id = 1; id <= 2; id++)
              {
                'id': id,
                'text': 'Aviso $id',
                'created_at': 1,
                'read_at': marked.contains(id) ? 1 : null,
                'link': '#/admin',
              },
          ],
        });
      }),
    );
    final session = SessionController(api);
    await tester.pumpWidget(
      MaterialApp(home: NotificationsScreen(session, PhotoPickerService())),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Aviso 1'));
    await tester.pumpAndSettle();
    expect(marked, [1]);
    expect(find.byIcon(Icons.notifications_active_outlined), findsOneWidget);
    final before = reads;
    await tester.pump(const Duration(seconds: 16));
    await tester.pumpAndSettle();
    expect(reads, before + 1);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(seconds: 6));
    await tester.pumpAndSettle();
    expect(reads, before + 1);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(reads, before + 2);
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
    api.close();
  });

  testWidgets('Contadores se actualizan y no consultan en segundo plano', (
    tester,
  ) async {
    var reads = 0;
    final api = ApiClient(
      client: MockClient((r) async {
        if (r.url.path == '/api/me') {
          reads++;
          return json({
            'user': fixtures.user,
            'unread_messages': reads,
            'unread_notifications': reads,
            'csrf_token': 'csrf',
          });
        }
        if (r.url.path == '/api/meta') return json(fixtures.meta);
        if (r.url.path == '/api/posts') {
          return json({'posts': [], 'page': 1, 'pages': 1, 'total': 0});
        }
        return json({});
      }),
    );
    await tester.pumpWidget(EcoGalloApp(api: api));
    await tester.pumpAndSettle();
    expect(reads, 1);
    expect(find.text('2'), findsOneWidget);
    await tester.pump(const Duration(seconds: 6));
    await tester.pumpAndSettle();
    expect(reads, 2);
    expect(find.text('4'), findsOneWidget);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(seconds: 61));
    await tester.pumpAndSettle();
    expect(reads, 2);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(reads, 3);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Un sondeo pendiente no oculta el mensaje recién enviado', (
    tester,
  ) async {
    final oldPoll = Completer<http.Response>();
    var reads = 0, sent = false;
    final api = ApiClient(
      client: MockClient((r) async {
        if (r.url.path == '/api/me') {
          return json({'user': fixtures.user, 'csrf_token': 'csrf'});
        }
        if (r.url.path == '/api/messages') {
          sent = true;
          return json({});
        }
        if (++reads == 2) return oldPoll.future;
        return json({
          'other': {'name': 'Compañero'},
          'post': fixtures.post,
          'meeting_points': <String>[],
          'messages': [
            if (sent)
              {
                'id': 1,
                'sender_id': 1,
                'content': 'Mensaje nuevo',
                'created_at': 1,
              },
          ],
        });
      }),
    );
    await tester.pumpWidget(MaterialApp(home: ChatScreen(api, 2, 2)));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 1));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.enterText(
      find.byKey(const Key('chat-input')),
      'Mensaje nuevo',
    );
    await tester.tap(find.byKey(const Key('send-message')));
    await tester.pump();
    await tester.pump();
    expect(sent, true);
    oldPoll.complete(
      json({
        'other': {'name': 'Compañero'},
        'post': fixtures.post,
        'meeting_points': <String>[],
        'messages': <Object>[],
      }),
    );
    await tester.pumpAndSettle();
    expect(reads, 3);
    expect(find.text('Mensaje nuevo'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    api.close();
  });
}

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/core/session_controller.dart';
import 'package:eco_gallo_mobile/features/posts/post_editor_screen.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/photo_picker_service.dart';
import 'package:eco_gallo_mobile/models/models.dart';
import 'package:eco_gallo_mobile/repositories/catalog_repository.dart';

void main() {
  testWidgets('Valida campos fuera de pantalla antes de enviar un formulario', (
    tester,
  ) async {
    var submitted = 0;
    final api = ApiClient(
      client: MockClient((_) async {
        submitted++;
        return http.Response('{}', 200);
      }),
    );
    final session = SessionController(api)
      ..phase = SessionPhase.signedIn
      ..meta = {
        'categories': ['Libros'],
        'centros': ['General'],
        'tipos': ['venta', 'trueque', 'donacion'],
        'conditions': ['Usado'],
      };
    await tester.pumpWidget(
      MaterialApp(home: PostEditorScreen(session, PhotoPickerService())),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('save-post')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('save-post')));
    await tester.pumpAndSettle();
    expect(submitted, 0);
    expect(find.text('Escribe al menos 3 caracteres.'), findsOneWidget);
    expect(find.text('Escribe al menos 10 caracteres.'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('post-price')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('post-price')), '0');
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.ensureVisible(find.byKey(const Key('save-post')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('save-post')));
    await tester.pumpAndSettle();
    expect(find.textContaining('El precio debe ser mayor a 0'), findsOneWidget);
    expect(submitted, 0);
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
    api.close();
  });
  test(
    'Fotos: rechaza exceso, formato no admitido y tamaño antes de subir',
    () async {
      final png = XFile.fromData(
        Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0]),
        name: 'photo.png',
      );
      await validatePhotos([png], maxCount: 5, maxBytes: 5 * 1024 * 1024);
      await expectLater(
        validatePhotos(
          List.filled(6, png),
          maxCount: 5,
          maxBytes: 5 * 1024 * 1024,
        ),
        throwsA(isA<ApiException>()),
      );
      await expectLater(
        validatePhotos([png], maxCount: 5, maxBytes: 5),
        throwsA(isA<ApiException>()),
      );
      final fake = XFile.fromData(
        Uint8List.fromList(utf8.encode('no es una foto')),
        name: 'photo.jpg',
      );
      await expectLater(
        validatePhotos([fake], maxCount: 5, maxBytes: 1024),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test(
    'Multipart envía cookie, CSRF, campos e imagen sin forzar JSON',
    () async {
      final temp = await Directory.systemTemp.createTemp('ecogallo-upload-');
      final photo = File('${temp.path}/photo.png');
      await photo.writeAsBytes([137, 80, 78, 71, 13, 10, 26, 10]);
      http.Request? uploaded;
      final api = ApiClient(
        client: MockClient((request) async {
          if (request.url.path == '/api/me') {
            return http.Response(
              '{"csrf_token":"csrf-image"}',
              200,
              headers: {'set-cookie': 'eg_session=opaque; HttpOnly'},
            );
          }
          uploaded = request;
          return http.Response('{"id":42}', 201);
        }),
      );
      try {
        expect(
          await CatalogRepository(api).save(
            {'title': 'Libro móvil', 'tipo': 'venta', 'price': '20.50'},
            [XFile(photo.path)],
          ),
          42,
        );
        expect(uploaded!.headers['Cookie'], 'eg_session=opaque');
        expect(uploaded!.headers['X-CSRF-Token'], 'csrf-image');
        expect(
          uploaded!.headers['content-type'],
          startsWith('multipart/form-data; boundary='),
        );
        final payload = utf8.decode(uploaded!.bodyBytes, allowMalformed: true);
        expect(payload, contains('name="images"'));
        expect(payload, contains('name="title"'));
        expect(payload, contains('Libro móvil'));
        expect(payload, contains('20.50'));
      } finally {
        api.close();
        await temp.delete(recursive: true);
      }
    },
  );
  test('Estados reservados y vendidos no habilitan edición', () {
    for (final state in [
      'pending',
      'active',
      'paused',
      'reserved',
      'sold',
      'removed',
    ]) {
      final post = Post.fromJson({
        'id': 1,
        'title': 'Libro',
        'category': 'Libros',
        'tipo': 'venta',
        'status': state,
        'author': {'id': 1},
      });
      expect(post.canEdit, ['pending', 'active', 'paused'].contains(state));
    }
  });
}

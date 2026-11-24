import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/photo_picker_service.dart';

class TestPhotos extends PhotoPickerService {
  TestPhotos(this.files);
  final List<XFile> files;
  int index = 0;
  @override
  void startRecovery() {}
  @override
  Future<List<XFile>> takeRecovered() async => [];
  @override
  Future<List<XFile>> pick({int limit = 5}) async {
    if (const bool.fromEnvironment('NATIVE_PICKER_CHECK') && index == 0) {
      index++;
      debugPrint('NATIVE_PHOTO_PICKER_READY');
      return super.pick(limit: limit);
    }
    return [files[(index++).clamp(0, files.length - 1)]];
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Publicar foto, editar, moderar, pausar y proteger propiedad', (
    tester,
  ) async {
    final temp = await Directory.systemTemp.createTemp('ecogallo-native-');
    final files = <XFile>[];
    for (var i = 0; i < 2; i++) {
      final recorder = ui.PictureRecorder();
      final canvas = ui.Canvas(recorder);
      canvas.drawColor(
        i == 0 ? const ui.Color(0xff1d5c3a) : const ui.Color(0xffc28634),
        ui.BlendMode.src,
      );
      final picture = recorder.endRecording();
      final image = await picture.toImage(64, 64);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      final file = File('${temp.path}/material-$i.png');
      await file.writeAsBytes(bytes!.buffer.asUint8List());
      files.add(XFile(file.path));
      image.dispose();
      picture.dispose();
    }
    final owner = ApiClient(), admin = ApiClient(), other = ApiClient();
    try {
      await owner.post('/api/auth/login', {
        'email': 'editor@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      await admin.post('/api/auth/login', {
        'email': 'revisor@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      await other.post('/api/auth/login', {
        'email': 'otro@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      Future<void> waitFor(Finder finder, {int attempts = 200}) async {
        for (var i = 0; i < attempts; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (finder.evaluate().isNotEmpty) {
            await tester.pumpAndSettle();
            return;
          }
        }
        expect(finder, findsWidgets);
      }

      Future<void> visible(Finder finder) async {
        FocusManager.instance.primaryFocus?.unfocus();
        await tester.pumpAndSettle();
        if (finder.evaluate().isEmpty) {
          await tester.scrollUntilVisible(
            finder,
            200,
            scrollable: find.byType(Scrollable).first,
          );
        } else {
          await tester.ensureVisible(finder);
        }
        await tester.pumpAndSettle();
      }

      Future<void> tapKey(String key) async {
        final finder = find.byKey(Key(key));
        await visible(finder);
        await tester.tap(finder);
        await tester.pumpAndSettle();
      }

      Future<void> enter(String key, String value) async {
        final finder = find.byKey(Key(key));
        await visible(finder);
        await tester.enterText(finder, value);
        FocusManager.instance.primaryFocus?.unfocus();
        await tester.pumpAndSettle();
      }

      Future<void> choose(String key, String label) async {
        await tapKey(key);
        await tester.tap(find.text(label).last);
        await tester.pumpAndSettle();
      }

      Future<Map<String, dynamic>> ownPost(int id) async =>
          (await owner.get('/api/posts/$id'))['post'] as Map<String, dynamic>;
      Future<bool> inCatalog(int id) async =>
          ((await owner.get('/api/posts'))['posts'] as List).any(
            (p) => p['id'] == id,
          );
      final title = 'Material móvil ${DateTime.now().millisecondsSinceEpoch}';
      await tester.pumpWidget(EcoGalloApp(photoPicker: TestPhotos(files)));
      await waitFor(find.byKey(const Key('email')));
      await enter('email', 'editor@edu.uaa.mx');
      await enter('password', 'PruebaMovil123');
      await tapKey('sign-in');
      await waitFor(find.byKey(const Key('catalog-create')));
      await tapKey('catalog-create');
      await enter('post-title', title);
      await enter(
        'post-description',
        'Material de prueba en buen estado para reutilizar en clase.',
      );
      await choose('post-category', 'Libros');
      await enter('post-price', '199.50');
      await tapKey('pick-photos');
      await waitFor(find.textContaining('1/5 seleccionadas'), attempts: 1800);
      expect(find.textContaining('1/5 seleccionadas'), findsOneWidget);
      await tapKey('save-post');
      await waitFor(find.text('Mis publicaciones'));
      var mine =
          (await owner.get('/api/posts', {'mine': '1'}))['posts'] as List;
      final created =
          mine.firstWhere((p) => p['title'] == title) as Map<String, dynamic>;
      final id = created['id'] as int;
      final firstImage = (created['images'] as List).single;
      expect(created['status'], 'pending');
      expect(created['price_cents'], 19950);
      expect(await inCatalog(id), false);
      await expectLater(
        other.get('/api/posts/$id'),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
      );
      await expectLater(
        other.post('/api/posts/$id/pause', {'paused': true}),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
      );
      await expectLater(
        other.post('/api/admin/posts/$id/moderate', {'action': 'approve'}),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
      );
      await tapKey('edit-$id');
      await enter('post-title', '$title editado');
      await tapKey('save-post');
      await waitFor(find.text('$title editado'));
      expect((await ownPost(id))['images'], [firstImage]);
      await admin.post('/api/admin/posts/$id/moderate', {'action': 'approve'});
      await tester.tap(find.byTooltip('Actualizar'));
      await tester.pumpAndSettle();
      await waitFor(find.text('Disponible'));
      expect(await inCatalog(id), true);
      await tapKey('pause-$id');
      await waitFor(find.text('Pausado'));
      expect(await inCatalog(id), false);
      await tapKey('pause-$id');
      await waitFor(find.text('Disponible'));
      expect(await inCatalog(id), true);
      await tapKey('edit-$id');
      await tapKey('pick-photos');
      await tapKey('save-post');
      await waitFor(find.text('En revisión'));
      final replaced = await ownPost(id);
      expect((replaced['images'] as List).single, isNot(firstImage));
      expect(await inCatalog(id), false);
      for (final entry in {
        'donacion': 'Donación',
        'trueque': 'Trueque',
      }.entries) {
        await tapKey('create-post');
        await enter('post-title', '${entry.value} móvil');
        await enter(
          'post-description',
          'Material para compartir con la comunidad universitaria.',
        );
        await choose('post-category', 'Libros');
        await choose('post-type', entry.value);
        expect(find.byKey(const Key('post-price')), findsNothing);
        await tapKey('save-post');
        await waitFor(find.text('${entry.value} móvil'));
        mine = (await owner.get('/api/posts', {'mine': '1'}))['posts'] as List;
        final posted = mine.firstWhere(
          (p) => p['title'] == '${entry.value} móvil',
        );
        expect(posted['price_cents'], 0);
        expect(posted['tipo'], entry.key);
        expect(posted['status'], 'pending');
      }
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    } finally {
      owner.close();
      admin.close();
      other.close();
      await temp.delete(recursive: true);
    }
  });
}

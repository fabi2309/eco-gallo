import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/photo_picker_service.dart';

class ProfilePhotos extends PhotoPickerService {
  ProfilePhotos(this.photo);
  final XFile photo;
  @override
  void startRecovery() {}
  @override
  Future<List<XFile>> takeRecovered() async => [];
  @override
  Future<List<XFile>> pick({int limit = 5}) async => [photo];
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Comunidad, perfil, notificaciones y ciclo de pedidos simulados',
    (tester) async {
      binding.testTextInput.register();
      addTearDown(binding.testTextInput.unregister);
      final buyer = ApiClient(),
          seller = ApiClient(),
          admin = ApiClient(),
          stranger = ApiClient();
      final temp = await Directory.systemTemp.createTemp('ecogallo-community-');
      final recorder = ui.PictureRecorder();
      ui.Canvas(recorder)
          .drawColor(const ui.Color(0xff285d40), ui.BlendMode.src);
      final picture = recorder.endRecording();
      final image = await picture.toImage(64, 64);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      final avatar = File('${temp.path}/perfil.png');
      await avatar.writeAsBytes(bytes!.buffer.asUint8List());
      image.dispose();
      picture.dispose();
      try {
        for (final entry in {
          buyer: 'otro',
          seller: 'editor',
          admin: 'revisor',
          stranger: 'curioso',
        }.entries) {
          await entry.key.post('/api/auth/login', {
            'email': '${entry.value}@edu.uaa.mx',
            'password': 'PruebaMovil123',
          });
        }
        final buyerId = (await buyer.get('/api/me'))['user']['id'] as int;
        final sellerId = (await seller.get('/api/me'))['user']['id'] as int;
        final catalog = (await buyer.get('/api/posts'))['posts'] as List;
        int postId(String title) =>
            catalog.firstWhere((p) => p['title'] == title)['id'] as int;
        final saleId = postId('Libro venta móvil');
        Future<void> waitFor(Finder finder) async {
          for (var i = 0; i < 300; i++) {
            await tester.pump(const Duration(milliseconds: 100));
            if (finder.evaluate().isNotEmpty) {
              await tester.pumpAndSettle();
              return;
            }
          }
          expect(finder, findsWidgets);
        }

        Future<void> visible(Finder finder, {Finder? scrollable}) async {
          FocusManager.instance.primaryFocus?.unfocus();
          await tester.pumpAndSettle();
          if (finder.evaluate().isEmpty) {
            await tester.scrollUntilVisible(
              finder,
              220,
              scrollable: scrollable ?? find.byType(Scrollable).first,
            );
          } else {
            await tester.ensureVisible(finder);
          }
          await tester.pumpAndSettle();
        }

        Future<void> tap(Finder finder, {Finder? scrollable}) async {
          await visible(finder, scrollable: scrollable);
          await tester.tap(finder);
          await tester.pumpAndSettle();
        }

        Future<void> tapKey(String key) => tap(find.byKey(Key(key)));
        Future<void> enter(String key, String value) async {
          final finder = find.byKey(Key(key));
          await visible(finder);
          await tester.enterText(finder, value);
          if (key == 'search') {
            expect(tester.widget<TextField>(finder).controller!.text, value);
          }
          FocusManager.instance.primaryFocus?.unfocus();
          await tester.pumpAndSettle();
        }

        Future<void> home() async {
          bool currentCatalog() => find
              .byKey(const Key('open-menu'))
              .evaluate()
              .any((element) => ModalRoute.of(element)?.isCurrent == true);
          for (var i = 0; i < 6 && !currentCatalog(); i++) {
            await tester.pageBack();
            await tester.pumpAndSettle();
          }
          await waitFor(find.byKey(const Key('open-menu')));
          expect(currentCatalog(), true);
        }

        Future<void> menu(String label) async {
          await home();
          await tapKey('open-menu');
          await tap(
            find.byKey(Key('menu-$label')),
            scrollable: find
                .descendant(
                  of: find.byType(Drawer),
                  matching: find.byType(Scrollable),
                )
                .first,
          );
        }

        Future<void> openPost(int id, String title) async {
          await home();
          await enter('search', title);
          await tester.pump(const Duration(milliseconds: 500));
          await tester.pumpAndSettle();
          await waitFor(find.byKey(Key('post-$id')));
          await tapKey('post-$id');
          await waitFor(find.byKey(const Key('detail-title')));
        }

        Future<int> buy(int pid, String title) async {
          await openPost(pid, title);
          await tapKey('buy-demo');
          await waitFor(find.byKey(const Key('checkout-method')));
          await tapKey('checkout-method');
          await tap(find.text('Tarjeta ficticia · simulación').last);
          await enter('card-holder', 'Persona de prueba');
          await enter('card-last4', '4242');
          await tapKey('confirm-checkout');
          await tap(find.text('Confirmar'));
          await waitFor(find.byKey(const Key('order-status')));
          expect(find.text('Pago retenido'), findsOneWidget);
          return ((await buyer.get('/api/orders'))['orders'] as List)
                  .firstWhere((o) => o['post_id'] == pid)['id']
              as int;
        }

        await tester.pumpWidget(
          EcoGalloApp(photoPicker: ProfilePhotos(XFile(avatar.path))),
        );
        await waitFor(find.byKey(const Key('email')));
        await enter('email', 'otro@edu.uaa.mx');
        await enter('password', 'PruebaMovil123');
        await tapKey('sign-in');
        await waitFor(find.byKey(const Key('open-menu')));
        await openPost(saleId, 'Libro venta móvil');
        await tapKey('toggle-favorite');
        expect(
          (await buyer.get('/api/favorites'))['post_ids'],
          contains(saleId),
        );
        await tapKey('contact-author');
        await waitFor(find.byKey(const Key('chat-input')));
        await enter(
          'chat-input',
          'Hola, podemos acordar la entrega en La Velaria.',
        );
        await tapKey('send-message');
        final incoming = await seller.get('/api/threads/$saleId/$buyerId');
        expect(incoming['post']['author_id'], sellerId);
        expect(
          (incoming['messages'] as List).last['content'],
          contains('La Velaria'),
        );
        await seller.post('/api/messages', {
          'post_id': saleId,
          'receiver_id': buyerId,
          'content': 'Sí, nos vemos en La Velaria.',
        });
        await waitFor(find.text('Sí, nos vemos en La Velaria.'));
        expect((await buyer.get('/api/me'))['unread_messages'], 0);
        await tester.pageBack();
        await tester.pumpAndSettle();
        await tapKey('buy-demo');
        await waitFor(find.byKey(const Key('checkout-method')));
        await tapKey('checkout-method');
        await tap(find.text('Tarjeta ficticia · simulación').last);
        await enter('card-holder', 'Persona de prueba');
        await enter('card-last4', '4242');
        await tapKey('confirm-checkout');
        await tap(find.text('Confirmar'));
        await waitFor(find.byKey(const Key('order-status')));
        final orderId =
            ((await buyer.get('/api/orders'))['orders'] as List).first['id']
                as int;
        await expectLater(
          stranger.get('/api/orders/$orderId'),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
        );
        await expectLater(
          buyer.post('/api/orders/$orderId/deliver', {'simulation_only': true}),
          throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
        );
        await seller.post('/api/orders/$orderId/deliver', {
          'simulation_only': true,
        });
        await tap(find.byTooltip('Actualizar'));
        await waitFor(find.text('Entrega indicada'));
        await tapKey('order-action-confirm');
        await tap(find.text('Confirmar'));
        await waitFor(find.text('Completado'));
        expect((await seller.get('/api/wallet'))['available_cents'], 10000);
        expect(
          (await buyer.get('/api/posts/$saleId'))['post']['status'],
          'sold',
        );
        await menu('Favoritos');
        await waitFor(find.byKey(Key('favorite-$saleId')));
        await tap(find.byTooltip('Quitar de favoritos'));
        expect((await buyer.get('/api/favorites'))['post_ids'], isEmpty);
        await menu('Lista de deseos');
        await waitFor(find.byKey(const Key('wish-term')));
        await enter('wish-term', 'material especial');
        await tapKey('add-wish');
        expect(((await buyer.get('/api/wishlist'))['items'] as List).length, 1);
        final special = await seller.multipart('POST', '/api/posts', {
          'title': 'Material especial móvil',
          'description':
              'Material especial para la comunidad de la universidad.',
          'category': 'Libros',
          'centro': 'General',
          'condition': 'Usado',
          'tipo': 'donacion',
          'price': '0',
        }, []);
        await admin.post('/api/admin/posts/${special['id']}/moderate', {
          'action': 'approve',
        });
        await menu('Notificaciones');
        await waitFor(find.textContaining('Material especial móvil'));
        await tap(find.textContaining('Material especial móvil').first);
        await waitFor(find.byKey(const Key('detail-title')));
        expect(find.text('Material especial móvil'), findsOneWidget);
        await tester.pageBack();
        await tester.pumpAndSettle();
        await tapKey('read-notifications');
        expect(
          ((await buyer.get('/api/notifications'))['notifications'] as List)
              .every((n) => n['read_at'] != null),
          true,
        );
        await menu('Mi perfil');
        await waitFor(find.byKey(const Key('edit-profile-name')));
        await tap(find.text('Cambiar foto'));
        await tester.pumpAndSettle();
        expect((await buyer.get('/api/me'))['user']['avatar'], isNotEmpty);
        await enter('edit-profile-name', 'Estudiante Móvil');
        await enter(
          'edit-profile-bio',
          'Reutilizando materiales para la tesina.',
        );
        await tapKey('save-profile');
        expect(
          (await buyer.get('/api/me'))['user']['name'],
          'Estudiante Móvil',
        );
        await menu('Mi actividad');
        await waitFor(find.text('Mi actividad'));
        expect(
          ((await buyer.get('/api/activity'))['items'] as List).isNotEmpty,
          true,
        );
        await menu('Impacto');
        await waitFor(find.text('Impacto de la comunidad'));
        expect(
          (await buyer.get('/api/impact'))['reused_items'],
          greaterThanOrEqualTo(1),
        );
        await menu('Saldo');
        await waitFor(find.text('Liberado por ventas'));
        final refundId = await buy(
          postId('Libro reembolso móvil'),
          'Libro reembolso móvil',
        );
        await seller.post('/api/orders/$refundId/refund', {
          'simulation_only': true,
        });
        await tap(find.byTooltip('Actualizar'));
        await waitFor(find.text('Reembolsado'));
        final disputeId = await buy(
          postId('Libro disputa móvil'),
          'Libro disputa móvil',
        );
        await tapKey('order-action-dispute');
        await enter(
          'action-reason',
          'El material de prueba no coincide con lo acordado.',
        );
        await tap(find.text('Continuar'));
        await waitFor(find.text('En disputa'));
        expect(find.byKey(const Key('order-action-confirm')), findsNothing);
        await admin.post('/api/orders/$disputeId/resolve-refund', {
          'simulation_only': true,
        });
        await tap(find.byTooltip('Actualizar'));
        await waitFor(find.text('Reembolsado'));
        await home();
        await tap(find.byTooltip('Cerrar sesión'));
        await waitFor(find.byKey(const Key('email')));
        await enter('email', 'editor@edu.uaa.mx');
        await enter('password', 'PruebaMovil123');
        await tapKey('sign-in');
        await waitFor(find.byKey(const Key('my-posts')));
        await tapKey('my-posts');
        final donationId = postId('Donación móvil de prueba');
        await tap(
          find.descendant(
            of: find.byKey(Key('my-post-$donationId')),
            matching: find.text('Marcar entregado'),
          ),
        );
        await tap(find.text('Confirmar'));
        expect(
          (await seller.get('/api/posts/$donationId'))['post']['status'],
          'sold',
        );
        expect((await seller.get('/api/wallet'))['available_cents'], 10000);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      } finally {
        buyer.close();
        seller.close();
        admin.close();
        stranger.close();
        await temp.delete(recursive: true);
      }
    },
  );
}

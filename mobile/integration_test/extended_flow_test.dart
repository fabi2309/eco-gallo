import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Términos, teléfono, carrito, efectivo y tarjeta ficticia', (
    tester,
  ) async {
    binding.testTextInput.register();
    final seller = ApiClient(), buyer = ApiClient();
    Future<void> waitFor(Finder finder) async {
      for (var i = 0; i < 250; i++) {
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
      final drawerScroll = find.descendant(
        of: find.byType(Drawer),
        matching: find.byType(Scrollable),
      );
      if (finder.evaluate().isEmpty) {
        await tester.scrollUntilVisible(
          finder,
          180,
          scrollable: drawerScroll.evaluate().isNotEmpty
              ? drawerScroll.first
              : find.byType(Scrollable).first,
        );
      } else {
        await tester.ensureVisible(finder);
      }
      await tester.pumpAndSettle();
    }

    Future<void> tap(Finder f) async {
      await visible(f);
      await tester.tap(f);
      await tester.pumpAndSettle();
    }

    Future<void> key(String k) => tap(find.byKey(Key(k)));
    Future<void> enter(String k, String value) async {
      final f = find.byKey(Key(k));
      await visible(f);
      await tester.enterText(f, value);
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
    }

    Future<void> home() async {
      for (var i = 0; i < 8; i++) {
        final roots = find.byKey(const Key('open-menu')).evaluate();
        if (roots.any((e) => ModalRoute.of(e)?.isCurrent == true)) return;
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
      fail('No regresó al catálogo');
    }

    Future<void> menu(String label) async {
      await home();
      await key('open-menu');
      await key('menu-$label');
    }

    Future<void> open(int id, String title) async {
      await home();
      await enter('search', title);
      await waitFor(find.byKey(Key('post-$id')));
      await key('post-$id');
      await waitFor(find.byKey(const Key('detail-title')));
    }

    try {
      await seller.post('/api/auth/login', {
        'email': 'editor@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      await buyer.post('/api/auth/login', {
        'email': 'curioso@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      final catalog = (await seller.get('/api/posts'))['posts'] as List;
      int id(String title) =>
          catalog.firstWhere((p) => p['title'] == title)['id'] as int;
      await tester.pumpWidget(const EcoGalloApp());
      await waitFor(find.byKey(const Key('email')));
      await enter('email', 'curioso@edu.uaa.mx');
      await enter('password', 'PruebaMovil123');
      await key('sign-in');
      await waitFor(find.byKey(const Key('accept-terms')));
      await tap(find.text('Aviso de privacidad'));
      expect(find.textContaining('Responsable'), findsWidgets);
      await key('accept-terms');
      await waitFor(find.byKey(const Key('open-menu')));
      expect((await buyer.get('/api/me'))['needs_terms'], false);
      await menu('Teléfono y cobros');
      await waitFor(find.byKey(const Key('payment-phone')));
      await enter('payment-phone', '4495557788');
      await tap(find.text('Solicitar código'));
      await waitFor(find.byKey(const Key('phone-dev-code')));
      final text = tester
          .widget<SelectableText>(find.byKey(const Key('phone-dev-code')))
          .data!;
      await enter('payment-code', RegExp(r'\d{6}').firstMatch(text)!.group(0)!);
      await key('verify-phone');
      await enter('payout-holder', 'Persona de prueba');
      await enter('payout-last4', '4242');
      await key('save-payout');
      expect(
        (await buyer.get('/api/me'))['user']['payments']['payout']['last4'],
        '4242',
      );
      final first = id('Libro venta móvil'), second = id('Libro disputa móvil');
      await open(first, 'Libro venta móvil');
      await key('add-cart');
      await open(second, 'Libro disputa móvil');
      await key('add-cart');
      await menu('Carrito');
      await waitFor(find.byKey(const Key('cart-checkout')));
      await key('cart-checkout');
      await waitFor(find.byKey(const Key('confirm-checkout')));
      await key('confirm-checkout');
      await tap(find.text('Confirmar'));
      await waitFor(find.text('Compras y ventas'));
      final orders = (await buyer.get('/api/orders'))['orders'] as List;
      expect(orders.length, 2);
      expect(orders.every((o) => o['status'] == 'CASH_PENDING'), true);
      final completed = orders.first['id'] as int,
          cancelled = orders.last['id'] as int;
      await seller.post('/api/orders/$completed/cash-received', {
        'simulation_only': true,
      });
      await tap(find.byTooltip('Actualizar'));
      await key('order-$completed');
      await waitFor(find.byKey(const Key('order-status')));
      expect(find.text('Completado'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await key('order-$cancelled');
      await key('order-action-cancel_cash');
      await tap(find.text('Confirmar'));
      await waitFor(find.text('Cancelado'));
      expect((await buyer.get('/api/cart'))['items'], isEmpty);
      final cardPost = id('Libro reembolso móvil');
      await open(cardPost, 'Libro reembolso móvil');
      await key('buy-demo');
      await waitFor(find.byKey(const Key('checkout-method')));
      await key('checkout-method');
      await tap(find.text('Tarjeta ficticia · simulación').last);
      await enter('card-holder', 'Persona de prueba');
      await enter('card-last4', '4242');
      await key('confirm-checkout');
      await tap(find.text('Confirmar'));
      await waitFor(find.text('Pago retenido'));
      final cardOrder =
          ((await buyer.get('/api/orders'))['orders'] as List).firstWhere(
                (o) => o['post_id'] == cardPost,
              )['id']
              as int;
      await seller.post('/api/orders/$cardOrder/refund', {
        'simulation_only': true,
      });
      await menu('Privacidad y términos');
      await waitFor(find.text('Consultar y copiar mis datos'));
      await tap(find.text('Consultar y copiar mis datos'));
      await waitFor(find.text('Mis datos personales'));
      expect(find.byType(SelectableText), findsWidgets);
      await tap(find.text('Cerrar'));
      await menu('Impacto');
      await waitFor(find.textContaining('Ahorro económico estimado:'));
      expect((await buyer.get('/api/impact'))['monthly'], isNotEmpty);
      // Only the disposable fixture account is removed, after all its orders close.
      await menu('Privacidad y términos');
      await tap(find.text('Eliminar mi cuenta'));
      await waitFor(find.byKey(const Key('delete-word')));
      await enter('delete-password', 'PruebaMovil123');
      await enter('delete-word', 'ELIMINAR');
      await key('delete-confirm');
      await waitFor(find.byKey(const Key('email')));
      expect((await buyer.get('/api/me'))['user'], isNull);
      expect(tester.takeException(), isNull);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      seller.close();
      buyer.close();
      binding.testTextInput.unregister();
    }
  });
}

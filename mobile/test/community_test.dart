import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';

import 'dart:convert';

import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/features/catalog/detail_screen.dart';
import 'package:eco_gallo_mobile/features/orders/orders_screen.dart';
import 'package:eco_gallo_mobile/features/community/chat_screen.dart';

void main() {
  testWidgets('El móvil no ofrece comprar con proveedores externos', (
    tester,
  ) async {
    final api = ApiClient(
      client: MockClient((r) async {
        final body = r.url.path == '/api/me'
            ? {
                'user': {'id': 1},
              }
            : r.url.path == '/api/meta'
            ? {'payment_mode': 'live'}
            : {
                'post': {
                  'id': 2,
                  'title': 'Libro externo',
                  'description': 'Descripción de prueba',
                  'category': 'Libros',
                  'tipo': 'venta',
                  'status': 'active',
                  'price_cents': 10000,
                  'author': {'id': 2, 'name': 'Autor'},
                },
              };
        return http.Response(jsonEncode(body), 200);
      }),
    );
    await tester.pumpWidget(MaterialApp(home: DetailScreen(api, 2)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('buy-demo')), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    api.close();
  });
  testWidgets('Un pedido externo se consulta sin ejecutar acciones de pago', (
    tester,
  ) async {
    final api = ApiClient(
      client: MockClient(
        (r) async => http.Response(
          jsonEncode({
            'order': {
              'post_title': 'Libro',
              'status': 'HELD',
              'simulated': false,
              'amount_cents': 10000,
              'buyer': {'id': 1, 'name': 'Comprador'},
              'seller': {'id': 2, 'name': 'Vendedor'},
              'role': 'buyer',
              'created_at': 0,
              'actions': ['confirm', 'dispute', 'refund'],
              'events': [],
            },
          }),
          200,
        ),
      ),
    );
    await tester.pumpWidget(MaterialApp(home: OrderDetailScreen(api, 1)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('order-action-confirm')), findsNothing);
    expect(find.byKey(const Key('order-action-refund')), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    api.close();
  });
  testWidgets(
    'Chat admite teclado sin desbordamiento y limpia el temporizador al salir',
    (tester) async {
      tester.view.physicalSize = const Size(720, 1280);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetViewInsets);
      final api = ApiClient(
        client: MockClient(
          (r) async => http.Response(
            jsonEncode(
              r.url.path == '/api/me'
                  ? {
                      'user': {'id': 1},
                    }
                  : {
                      'other': {'name': 'Autor'},
                      'post': {'title': 'Libro'},
                      'messages': [],
                      'meeting_points': ['La Velaria'],
                    },
            ),
            200,
          ),
        ),
      );
      await tester.pumpWidget(MaterialApp(home: ChatScreen(api, 1, 2)));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('chat-input')), 'Hola');
      tester.view.viewInsets = const FakeViewPadding(bottom: 600);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      api.close();
    },
  );
}

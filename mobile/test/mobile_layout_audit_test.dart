import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/session_controller.dart';
import 'package:eco_gallo_mobile/core/photo_picker_service.dart';
import 'package:eco_gallo_mobile/models/models.dart';
import 'package:eco_gallo_mobile/features/auth/auth_screen.dart';
import 'package:eco_gallo_mobile/features/catalog/catalog_screen.dart';
import 'package:eco_gallo_mobile/features/catalog/detail_screen.dart';
import 'package:eco_gallo_mobile/features/community/chat_screen.dart';
import 'package:eco_gallo_mobile/features/community/community_screens.dart';
import 'package:eco_gallo_mobile/features/orders/orders_screen.dart';
import 'package:eco_gallo_mobile/features/posts/post_editor_screen.dart';
import 'package:eco_gallo_mobile/features/posts/my_posts_screen.dart';

const user = {
  'id': 1,
  'name': 'Estudiante de demostración con nombre extenso',
  'email': 'estudiante@edu.uaa.mx',
  'carrera': 'Ingeniería en Sistemas Computacionales',
  'centro': 'General',
  'bio': '',
  'avatar': '',
  'totp_enabled': false,
};
const post = {
  'id': 2,
  'title': 'Material universitario con descripción extensa para probar diferentes pantallas',
  'description': 'Material en buen estado para reutilizar en nuestra comunidad universitaria.',
  'category': 'Libros',
  'centro': 'General',
  'tipo': 'venta',
  'status': 'active',
  'condition': 'Usado',
  'price_cents': 1000000,
  'images': [],
  'author': {
    'id': 2,
    'name': 'Autor con nombre extenso',
    'carrera': 'Ingeniería en Sistemas Computacionales',
  },
};
const meta = {
  'categories': ['Libros', 'Electrónica'],
  'centros': ['General'],
  'tipos': ['venta', 'trueque', 'donacion'],
  'conditions': ['Usado'],
  'carreras': {
    'General': ['Ingeniería en Sistemas Computacionales'],
  },
  'payment_mode': 'demo',
};

ApiClient testApi({bool pending = false}) => ApiClient(
  client: MockClient((r) async {
    Object data;
    switch (r.url.path) {
      case '/api/health':
        data = {'ok': true};
      case '/api/meta':
        data = meta;
      case '/api/me':
        data = {
          'user': user,
          'csrf_token': 'test-csrf',
          'needs_verification': pending,
          'verification': {
            'note': 'Tu documentación está pendiente de revisión por parte de la administración.',
          },
        };
      case '/api/posts':
        data = {
          'posts': [post],
          'page': 1,
          'pages': 1,
          'total': 1,
        };
      case '/api/posts/2':
        data = {'post': post};
      case '/api/threads':
        data = {
          'threads': [
            {
              'post_id': 2,
              'post_title': post['title'],
              'other': {'id': 2, 'name': 'Nombre largo del compañero'},
              'last': {
                'content': 'Texto extenso del último mensaje para comprobar su presentación',
                'created_at': 1,
              },
              'unread': 123,
            },
          ],
        };
      case '/api/threads/2/2':
        data = {
          'other': {'name': 'Compañero con nombre extenso'},
          'post': post,
          'messages': [
            {
              'id': 1,
              'sender_id': 2,
              'content': 'Mensaje de prueba para revisar la orientación de la pantalla y el teclado.',
              'created_at': 1,
            },
          ],
          'meeting_points': ['Punto de Encuentro Central'],
        };
      case '/api/favorites':
        data = {
          'post_ids': [2],
        };
      case '/api/wishlist':
        data = {'items': [], 'max': 10};
      case '/api/notifications':
        data = {
          'notifications': [
            {
              'id': 1,
              'text': 'Hay una notificación importante con un texto largo para comprobar que puedes leerla completa.',
              'created_at': 1,
              'read_at': null,
              'link': '#/post/2',
            },
          ],
        };
      case '/api/orders':
        data = {'orders': [], 'page': 1, 'pages': 1};
      case '/api/orders/1':
        data = {
          'order': {
            'id': 1,
            'post_id': 2,
            'post_title': post['title'],
            'simulated': true,
            'amount_cents': 1000000,
            'status': 'HELD',
            'buyer': user,
            'seller': {'id': 2, 'name': 'Vendedor'},
            'role': 'buyer',
            'created_at': 1,
            'actions': ['confirm', 'dispute'],
            'events': [],
          },
        };
      case '/api/wallet':
        data = {
          'available_cents': 1000000,
          'pending_cents': 1000000,
          'buyer_held_cents': 1000000,
        };
      case '/api/activity':
        data = {'items': [], 'page': 1, 'pages': 1};
      case '/api/impact':
        data = {
          'users': 99999,
          'active_posts': 99999,
          'reused_items': 99999,
          'co2_kg': 99999.99,
          'posts_by_category': {'Libros': 99999},
        };
      default:
        data = {};
    }
    return http.Response(
      jsonEncode(data),
      200,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );
  }),
);

void main() {
  final screens = <String, Widget Function(ApiClient, SessionController)>{
    'Acceso': (api, s) => AuthScreen(s),
    'Perfil inicial': (api, s) => ProfileCompletionScreen(s),
    'Verificación pendiente': (api, s) =>
        EcoGalloApp(api: testApi(pending: true)),
    'Catálogo': (api, s) => CatalogScreen(s, PhotoPickerService()),
    'Detalle': (api, s) => DetailScreen(api, 2),
    'Publicar': (api, s) => PostEditorScreen(s, PhotoPickerService()),
    'Mis publicaciones': (api, s) => MyPostsScreen(s, PhotoPickerService()),
    'Chat': (api, s) => ChatScreen(api, 2, 2),
    'Bandeja': (api, s) => ThreadsScreen(api),
    'Favoritos': (api, s) => FavoritesScreen(api),
    'Deseos': (api, s) => WishlistScreen(s),
    'Notificaciones': (api, s) => NotificationsScreen(s, PhotoPickerService()),
    'Pedido': (api, s) => OrderDetailScreen(api, 1),
    'Perfil': (api, s) => ProfileScreen(s, PhotoPickerService()),
    'Saldo': (api, s) => WalletScreen(api),
    'Impacto': (api, s) => ImpactScreen(api),
  };
  for (final item in screens.entries) {
    testWidgets('Adaptación móvil: ${item.key}', (tester) async {
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetViewInsets);
      final api = testApi();
      final s = SessionController(api)
        ..meta = Map<String, dynamic>.from(meta)
        ..user = Student.fromJson(Map<String, dynamic>.from(user))
        ..phase = SessionPhase.signedIn;
      final screen = item.value(api, s);
      try {
        for (final scale in [1.0, 1.8]) {
          for (final size in [
            const Size(320, 568),
            const Size(568, 320),
            const Size(360, 640),
            const Size(640, 360),
          ]) {
            for (final keyboard in [false, true]) {
              tester.view.physicalSize = size;
              tester.view.viewInsets = FakeViewPadding(
                bottom: keyboard ? (size.height < 400 ? 160 : 280) : 0,
              );
              await tester.pumpWidget(
                MaterialApp(
                  builder: (context, child) => MediaQuery(
                    data: MediaQuery.of(context)
                        .copyWith(textScaler: TextScaler.linear(scale)),
                    child: child!,
                  ),
                  home: screen,
                ),
              );
              await tester.pumpAndSettle();
              expect(
                tester.takeException(),
                isNull,
                reason: '${item.key}: $size, texto $scale, teclado $keyboard',
              );
            }
          }
        }
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        s.dispose();
        api.close();
      }
    });
  }
}

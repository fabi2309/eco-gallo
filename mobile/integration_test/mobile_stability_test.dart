import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:http/http.dart' as http;
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';

class DisconnectableClient extends http.BaseClient {
  final inner = http.Client();
  bool offline = false;
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    if (offline) throw http.ClientException('Sin conexión de prueba');
    return inner.send(request);
  }

  @override
  void close() => inner.close();
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Android: giro real, teclado, borrador y salida sin red', (
    tester,
  ) async {
    final network = DisconnectableClient();
    final api = ApiClient(client: network);
    Future<void> waitFor(bool Function() ready) async {
      for (var i = 0; i < 150; i++) {
        await tester.pump(const Duration(milliseconds: 100));
        if (ready()) return;
      }
      expect(ready(), true);
    }

    Future<void> rotate(DeviceOrientation orientation) async {
      await SystemChrome.setPreferredOrientations([orientation]);
      await waitFor(() {
        final size = tester.view.physicalSize;
        return orientation == DeviceOrientation.portraitUp
            ? size.height > size.width
            : size.width > size.height;
      });
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }

    try {
      await rotate(DeviceOrientation.portraitUp);
      await api.post('/api/auth/login', {
        'email': 'editor@edu.uaa.mx',
        'password': 'PruebaMovil123',
      });
      await tester.pumpWidget(EcoGalloApp(api: api));
      await waitFor(
        () => find.byKey(const Key('open-menu')).evaluate().isNotEmpty,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('catalog-create')));
      await tester.pumpAndSettle();
      final field = find.byKey(const Key('post-title'));
      await tester.tap(field);
      await SystemChannels.textInput.invokeMethod<void>('TextInput.show');
      // Some emulators use only the computer's hardware keyboard. The widget
      // matrix separately checks layout with a visible IME in both orientations.
      await tester.pump(const Duration(seconds: 1));
      debugPrint('ANDROID_KEYBOARD_INSET=${tester.view.viewInsets.bottom}');
      final editable = find.descendant(
        of: field,
        matching: find.byType(EditableText),
      );
      tester
          .state<EditableTextState>(editable)
          .updateEditingValue(
            const TextEditingValue(
              text: 'Borrador tras girar',
              selection: TextSelection.collapsed(offset: 18),
            ),
          );
      await tester.pumpAndSettle();
      await rotate(DeviceOrientation.landscapeLeft);
      expect(
        tester.widget<TextFormField>(field).controller!.text,
        'Borrador tras girar',
      );
      await rotate(DeviceOrientation.portraitUp);
      expect(
        tester.widget<TextFormField>(field).controller!.text,
        'Borrador tras girar',
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await SystemChannels.textInput.invokeMethod<void>('TextInput.hide');
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Volver'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Salir sin guardar'));
      await tester.pumpAndSettle();
      network.offline = true;
      await tester.tap(find.byTooltip('Cerrar sesión'));
      await waitFor(
        () => find.byKey(const Key('sign-in')).evaluate().isNotEmpty,
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      // Local logout must also remove the cookie from the next real request.
      network.offline = false;
      expect((await api.get('/api/me'))['user'], isNull);
    } finally {
      network.offline = false;
      await tester.pumpWidget(const SizedBox.shrink());
      await SystemChrome.setPreferredOrientations([
        DeviceOrientation.portraitUp,
      ]);
      await tester.pump(const Duration(seconds: 1));
      await SystemChrome.setPreferredOrientations([]);
    }
    binding.testTextInput.unregister();
  });
}

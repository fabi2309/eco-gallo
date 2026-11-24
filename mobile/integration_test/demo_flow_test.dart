import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:eco_gallo_mobile/app.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Demo real: contraseña, búsqueda, detalle y logout', (
    tester,
  ) async {
    Future<void> waitFor(Finder finder) async {
      for (var i = 0; i < 200; i++) {
        await tester.pump(const Duration(milliseconds: 100));
        if (finder.evaluate().isNotEmpty) {
          await tester.pumpAndSettle();
          return;
        }
      }
      expect(finder, findsWidgets);
    }

    await tester.pumpWidget(const EcoGalloApp());
    await waitFor(find.byKey(const Key('email')));
    await tester.enterText(find.byKey(const Key('email')), 'movil@edu.uaa.mx');
    await tester.enterText(
      find.byKey(const Key('password')),
      'EcoGalloDemo123',
    );
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.ensureVisible(find.byKey(const Key('sign-in')));
    await tester.tap(find.byKey(const Key('sign-in')));
    await waitFor(find.byKey(const Key('search')));
    await tester.enterText(find.byKey(const Key('search')), 'Cálculo');
    FocusManager.instance.primaryFocus?.unfocus();
    await waitFor(find.text('Libro de Cálculo Vectorial'));
    await tester.ensureVisible(find.text('Libro de Cálculo Vectorial'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Libro de Cálculo Vectorial'));
    await waitFor(find.byKey(const Key('detail-title')));
    expect(find.text('Libro de Cálculo Vectorial'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Cerrar sesión'));
    await waitFor(find.byKey(const Key('email')));
    expect(tester.takeException(), isNull);
    await tester.tap(find.byKey(const Key('toggle-code')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('email')),
      'mobile-${DateTime.now().millisecondsSinceEpoch}@edu.uaa.mx',
    );
    await tester.ensureVisible(find.byKey(const Key('sign-in')));
    await tester.tap(find.byKey(const Key('sign-in')));
    await waitFor(find.byKey(const Key('dev-code')));
    final message = tester
        .widget<Text>(find.byKey(const Key('dev-code')))
        .data!;
    final code = RegExp(r'\d{6}').firstMatch(message)!.group(0)!;
    await tester.enterText(find.byKey(const Key('code')), code);
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.ensureVisible(find.byKey(const Key('sign-in')));
    await tester.tap(find.byKey(const Key('sign-in')));
    await waitFor(find.byKey(const Key('profile-name')));
    await tester.enterText(
      find.byKey(const Key('profile-name')),
      'Prueba Móvil',
    );
    FocusManager.instance.primaryFocus?.unfocus();
    final careerField = find.byKey(const Key('profile-career'));
    final career = tester
        .widget<DropdownButton<String>>(
          find.descendant(
            of: careerField,
            matching: find.byType(DropdownButton<String>),
          ),
        )
        .items!
        .first
        .value!;
    await tester.tap(careerField);
    await tester.pumpAndSettle();
    await tester.tap(find.text(career).last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Guardar y continuar'));
    await tester.tap(find.text('Guardar y continuar'));
    await waitFor(find.byKey(const Key('search')));
    await tester.tap(find.byTooltip('Cerrar sesión'));
    await waitFor(find.byKey(const Key('email')));
    expect(tester.takeException(), isNull);
  });
}

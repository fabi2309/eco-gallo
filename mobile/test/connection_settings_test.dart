import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences_platform_interface/in_memory_shared_preferences_async.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_async_platform_interface.dart';
import 'package:eco_gallo_mobile/core/api_client.dart';
import 'package:eco_gallo_mobile/core/connection_settings.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(
    () => SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.empty(),
  );

  test(
    'Solo el APK local acepta HTTP privado; HTTP público siempre se rechaza',
    () {
      for (final host in [
        '192.168.1.50',
        '10.1.2.3',
        '172.16.0.2',
        '172.31.255.254',
      ]) {
        if (ApiClient.localNetworkBuild) {
          expect(ApiClient.serverUri('http://$host:8080').host, host);
        } else {
          expect(
            () => ApiClient.serverUri('http://$host:8080'),
            throwsA(isA<ApiException>()),
          );
        }
      }
      for (final host in [
        'example.com',
        '8.8.8.8',
        '172.32.0.1',
        '169.254.1.1',
        '010.1.1.1',
        '[::1]',
      ]) {
        expect(
          () => ApiClient.serverUri('http://$host:8080'),
          throwsA(isA<ApiException>()),
        );
      }
      expect(ApiClient.serverUri('http://127.0.0.1:8080').host, '127.0.0.1');
    },
  );

  test('Recuerda la dirección, sin almacenar credenciales', () async {
    await ConnectionSettings().save('http://127.0.0.1:8080/');
    expect(await ConnectionSettings().load(), 'http://127.0.0.1:8080');
    await expectLater(
      ConnectionSettings().save('https://user:password@example.com'),
      throwsA(isA<ApiException>()),
    );
    expect(await ConnectionSettings().load(), 'http://127.0.0.1:8080');
  });

  test(
    'Ignora preferencias dañadas o no permitidas sin impedir el arranque',
    () async {
      await SharedPreferencesAsync().setString(
        ConnectionSettings.key,
        'javascript:void(0)',
      );
      expect(await ConnectionSettings().load(), isNull);
    },
  );
}

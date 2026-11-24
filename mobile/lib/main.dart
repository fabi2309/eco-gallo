import 'package:flutter/widgets.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'core/connection_settings.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = ConnectionSettings();
  final saved = await settings.load();
  runApp(
    EcoGalloApp(
      api: ApiClient(baseUrl: saved),
      saveServer: settings.save,
    ),
  );
}

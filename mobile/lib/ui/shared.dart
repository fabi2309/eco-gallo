import 'package:material_ui/material_ui.dart';

import '../core/session_controller.dart';
import '../core/api_client.dart';

const forest = Color(0xff1d5c3a);
const lime = Color(0xffb9dc4f);
const paper = Color(0xfff2f7ef);

class Brand extends StatelessWidget {
  const Brand({super.key});
  @override
  Widget build(BuildContext context) => FittedBox(
    fit: BoxFit.scaleDown,
    alignment: Alignment.centerLeft,
    child: const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.eco_rounded, color: forest, size: 34),
        SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'ECO-GALLO',
              style: TextStyle(
                fontWeight: FontWeight.w900,
                fontSize: 21,
                letterSpacing: 1,
              ),
            ),
            Text(
              'COMUNIDAD UAA',
              style: TextStyle(fontSize: 10, letterSpacing: 2, color: forest),
            ),
          ],
        ),
      ],
    ),
  );
}

class ErrorNotice extends StatelessWidget {
  const ErrorNotice(this.message, {super.key});
  final String? message;
  @override
  Widget build(BuildContext context) => message == null
      ? const SizedBox.shrink()
      : Container(
          width: double.infinity,
          margin: const EdgeInsets.symmetric(vertical: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xfffbe9e7),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(
            message!,
            style: const TextStyle(color: Color(0xff8e201d)),
          ),
        );
}

class PaymentNotice extends StatelessWidget {
  const PaymentNotice(this.mode, {super.key});
  final String mode;
  @override
  Widget build(BuildContext context) {
    if (mode == 'live') return const SizedBox.shrink();
    final text = switch (mode) {
      'demo' => 'Demostración · No se mueve dinero real',
      'test' => 'Stripe Test · Solo operaciones de prueba',
      _ => 'Pagos en línea deshabilitados',
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
      color: const Color(0xfff7f2cf),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 12, color: Color(0xff665716)),
      ),
    );
  }
}

Future<void> connectionDialog(
  BuildContext context,
  SessionController session,
) async {
  final controller = TextEditingController(text: session.api.baseUrl);
  String? error;
  bool saving = false;
  final route = DialogRoute<bool>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        scrollable: true,
        title: const Text('Conectar con ECO-GALLO'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Servidor encendido en la computadora. Wi-Fi: http://IP-DE-LA-PC:8080. USB: http://127.0.0.1:8080 después de ejecutar conectar_movil_usb.bat. La dirección se recuerda en este teléfono.',
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              enabled: !saving,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'Dirección del servidor',
              ),
            ),
            if (session.user != null)
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text('Cambiar de servidor cierra la sesión local.'),
              ),
            ErrorNotice(error),
          ],
        ),
        actions: [
          TextButton(
            onPressed: saving
                ? null
                : () => Navigator.pop(dialogContext, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: saving
                ? null
                : () async {
                    setState(() {
                      saving = true;
                      error = null;
                    });
                    try {
                      final address = ApiClient.serverUri(controller.text)
                          .origin;
                      await session.saveServer?.call(address);
                      if (!dialogContext.mounted) return;
                      session.api.setBaseUrl(address);
                      Navigator.pop(dialogContext, true);
                    } catch (e) {
                      if (dialogContext.mounted) {
                        setState(() {
                          error = e.toString();
                          saving = false;
                        });
                      }
                    }
                  },
            child: const Text('Conectar'),
          ),
        ],
      ),
    ),
  );
  final changed = await Navigator.of(context, rootNavigator: true).push(route);
  await route.completed;
  controller.dispose();
  if (changed == true) await session.initialize();
}

class ServerButton extends StatelessWidget {
  const ServerButton(this.session, {super.key});
  final SessionController session;
  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: 'Configurar conexión',
    onPressed: session.busy ? null : () => connectionDialog(context, session),
    icon: const Icon(Icons.settings_ethernet),
  );
}

class Photo extends StatelessWidget {
  const Photo(this.url, {super.key, this.width = 500});
  final Uri? url;
  final int width;
  @override
  Widget build(BuildContext context) {
    Widget fallback() => Container(
      color: const Color(0xffe1eadf),
      alignment: Alignment.center,
      child: const Icon(Icons.auto_stories_outlined, size: 48, color: forest),
    );
    return url == null
        ? fallback()
        : Image.network(
            url.toString(),
            fit: BoxFit.cover,
            cacheWidth: width,
            errorBuilder: (_, _, _) => fallback(),
            loadingBuilder: (_, image, progress) =>
                progress == null ? image : fallback(),
          );
  }
}

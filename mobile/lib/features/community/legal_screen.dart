import 'dart:convert';

import 'package:material_ui/material_ui.dart';

import '../../core/session_controller.dart';
import '../../ui/remote_page.dart';

class LegalScreen extends StatelessWidget {
  const LegalScreen(this.session, {super.key, this.requiredConsent = false});
  final SessionController session;
  final bool requiredConsent;
  Future<void> _deleteAccount(BuildContext context) async {
    final password = TextEditingController(),
        code = TextEditingController(),
        word = TextEditingController();
    final route = DialogRoute<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Eliminar mi cuenta'),
          scrollable: true,
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Se anonimizará tu cuenta y se retirará tu contenido. No podrás recuperar el acceso. No se permite con operaciones abiertas. Guarda antes una copia de tus datos.',
              ),
              TextField(
                key: const Key('delete-password'),
                controller: password,
                obscureText: true,
                maxLength: 128,
                decoration: const InputDecoration(
                  labelText: 'Contraseña (si tienes)',
                ),
              ),
              TextField(
                controller: code,
                maxLength: 12,
                decoration: const InputDecoration(
                  labelText: 'Código 2FA (si está activado)',
                ),
              ),
              TextField(
                key: const Key('delete-word'),
                controller: word,
                onChanged: (_) => update(() {}),
                decoration: const InputDecoration(
                  labelText: 'Escribe ELIMINAR para confirmar',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              key: const Key('delete-confirm'),
              onPressed: word.text.trim() != 'ELIMINAR'
                  ? null
                  : () => Navigator.pop(dialogContext, {
                      'confirm': word.text,
                      'password': password.text,
                      'code': code.text,
                    }),
              child: const Text('Eliminar definitivamente'),
            ),
          ],
        ),
      ),
    );
    final data = await Navigator.of(context).push(route);
    await route.completed;
    password.dispose();
    code.dispose();
    word.dispose();
    if (data == null) return;
    await session.api.request('DELETE', '/api/me', data: data);
    session.api.clearSession();
    await session.refreshSession();
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Privacidad y términos',
    load: () => session.api.get('/api/legal'),
    content: (context, data, state) => [
      Text('Versión ${data['version']} · ${data['operator']}'),
      for (final item in const {
        'privacy': 'Aviso de privacidad',
        'terms': 'Términos de uso',
      }.entries)
        ExpansionTile(
          title: Text(item.value),
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: SelectableText(
                '${(data['documents'] as Json? ?? {})[item.key] ?? 'Consulta los documentos completos en la web del servidor.'}',
              ),
            ),
          ],
        ),
      if (requiredConsent) ...[
        const Text(
          'Lee ambos documentos. Al aceptar se registra la versión vigente en tu cuenta.',
        ),
        FilledButton(
          key: const Key('accept-terms'),
          onPressed: state.busy
              ? null
              : () => state.run(() async {
                  await session.api.post('/api/me/terms', {
                    'accept': true,
                    'version': data['version'],
                  });
                  await session.refreshSession();
                }),
          child: const Text('Aceptar y continuar'),
        ),
        TextButton(
          onPressed: session.busy ? null : session.logout,
          child: const Text('Cerrar sesión'),
        ),
      ] else ...[
        OutlinedButton(
          onPressed: state.busy
              ? null
              : () => state.run(() async {
                  final export = await session.api.get('/api/me/export');
                  if (!context.mounted) return;
                  await showDialog<void>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Mis datos personales'),
                      scrollable: true,
                      content: SelectableText(
                        const JsonEncoder.withIndent('  ').convert(export),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Cerrar'),
                        ),
                      ],
                    ),
                  );
                }),
          child: const Text('Consultar y copiar mis datos'),
        ),
        TextButton(
          onPressed: state.busy
              ? null
              : () => state.run(() => _deleteAccount(context)),
          child: const Text('Eliminar mi cuenta'),
        ),
      ],
    ],
  );
}

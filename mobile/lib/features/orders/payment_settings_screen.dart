import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../ui/remote_page.dart';

class PaymentSettingsScreen extends StatefulWidget {
  const PaymentSettingsScreen(this.api, {super.key});
  final ApiClient api;
  @override
  State<PaymentSettingsScreen> createState() => _PaymentSettingsScreenState();
}

class _PaymentSettingsScreenState extends State<PaymentSettingsScreen> {
  final phone = TextEditingController(), code = TextEditingController();
  final holder = TextEditingController(), last4 = TextEditingController();
  String kind = 'tarjeta';
  String? devCode;
  bool requested = false;
  @override
  void dispose() {
    for (final c in [phone, code, holder, last4]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Teléfono y cobros',
    load: () async => {'user': await requireCurrentUser(widget.api)},
    content: (context, data, state) {
      final user = data['user'] as Json;
      final payments = user['payments'] as Json? ?? {};
      return [
        const Text(
          'El teléfono confirmado permite contactar a la otra persona durante una compra. La referencia de cobro solo guarda titular, tipo y últimos cuatro dígitos; no habilita transferencias bancarias.',
        ),
        Text(
          payments['phone_verified'] == true
              ? 'Teléfono confirmado: ${payments['phone']}'
              : 'Teléfono sin confirmar',
        ),
        TextField(
          key: const Key('payment-phone'),
          controller: phone,
          keyboardType: TextInputType.phone,
          maxLength: 16,
          decoration: const InputDecoration(
            labelText: 'Celular de México, 10 dígitos',
          ),
        ),
        OutlinedButton(
          onPressed: state.busy
              ? null
              : () => state.run(() async {
                  final result = await widget.api.post('/api/me/phone', {
                    'phone': phone.text,
                  });
                  if (!mounted) return;
                  setState(() {
                    requested = true;
                    devCode = result['dev_code'] as String?;
                  });
                }),
          child: const Text('Solicitar código'),
        ),
        if (requested) ...[
          if (devCode != null)
            SelectableText(
              'Solo desarrollo · código ficticio: $devCode',
              key: const Key('phone-dev-code'),
            ),
          TextField(
            key: const Key('payment-code'),
            controller: code,
            maxLength: 6,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Código de confirmación',
            ),
          ),
          FilledButton(
            key: const Key('verify-phone'),
            onPressed: state.busy
                ? null
                : () => state.run(() async {
                    await widget.api.post('/api/me/phone/verify', {
                      'code': code.text,
                    });
                    if (mounted) {
                      setState(() {
                        requested = false;
                        devCode = null;
                        code.clear();
                      });
                    }
                  }),
            child: const Text('Confirmar teléfono'),
          ),
        ],
        const Divider(height: 30),
        if (payments['payout'] != null)
          Text(
            'Referencia guardada: ${payments['payout']['kind']} · ${payments['payout']['last4']}',
          ),
        DropdownButtonFormField<String>(
          initialValue: kind,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Tipo de referencia'),
          items: const [
            DropdownMenuItem(
              value: 'tarjeta',
              child: Text('Tarjeta de débito'),
            ),
            DropdownMenuItem(value: 'clabe', child: Text('CLABE')),
          ],
          onChanged: state.busy ? null : (v) => kind = v ?? kind,
        ),
        TextField(
          key: const Key('payout-holder'),
          controller: holder,
          maxLength: 80,
          decoration: const InputDecoration(labelText: 'Titular'),
        ),
        TextField(
          key: const Key('payout-last4'),
          controller: last4,
          maxLength: 4,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Solo los últimos 4 dígitos',
          ),
        ),
        FilledButton(
          key: const Key('save-payout'),
          onPressed: state.busy || payments['phone_verified'] != true
              ? null
              : () => state.run(() async {
                  await widget.api.put('/api/me/payout', {
                    'kind': kind,
                    'holder': holder.text,
                    'last4': last4.text,
                  });
                }),
          child: const Text('Guardar referencia'),
        ),
      ];
    },
  );
}

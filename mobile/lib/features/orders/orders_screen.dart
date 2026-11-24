import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../ui/remote_page.dart';
import '../../ui/shared.dart';
import '../community/chat_screen.dart';

const orderStatuses = {
  'HELD': 'Pago retenido',
  'DELIVERED': 'Entrega indicada',
  'RELEASED': 'Completado',
  'DISPUTED': 'En disputa',
  'REFUNDED': 'Reembolsado',
  'CANCELLED': 'Cancelado',
  'PENDING_PAYMENT': 'Pago pendiente',
  'RELEASING': 'Liberación en proceso',
  'REFUNDING': 'Reembolso en proceso',
  'PAYMENT_REVIEW': 'Revisión administrativa',
};
const orderActionLabels = {
  'deliver': 'Marcar entrega',
  'confirm': 'Confirmar recepción',
  'dispute': 'Abrir disputa',
  'refund': 'Devolver pago simulado',
  'resolve_release': 'Resolver: liberar pago',
  'resolve_refund': 'Resolver: reembolsar',
};

class OrdersScreen extends StatefulWidget {
  const OrdersScreen(this.api, {super.key});
  final ApiClient api;
  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  int page = 1;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Compras y ventas',
    load: () =>
        widget.api.get('/api/orders', {'page': '$page', 'per_page': '20'}),
    content: (context, data, state) => [
      const Text(
        'Tus compras y ventas, con historial de entrega y resolución.',
      ),
      if ((data['orders'] as List).isEmpty)
        const Padding(
          padding: EdgeInsets.all(24),
          child: Text('Todavía no tienes pedidos.'),
        ),
      for (final order in data['orders'] as List)
        Card(
          child: ListTile(
            key: Key('order-${order['id']}'),
            title: Text(order['post_title'] as String),
            subtitle: Text(
              '${order['role'] == 'buyer' ? 'Compra' : 'Venta'} · ${money(order['amount_cents'])}\n${orderStatuses[order['status']] ?? 'En revisión'}${order['simulated'] == true ? ' · Simulación' : ''}',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () =>
                state.open(OrderDetailScreen(widget.api, order['id'] as int)),
          ),
        ),
      Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(
            tooltip: 'Página anterior',
            onPressed: state.loading || state.busy || page <= 1
                ? null
                : () {
                    page--;
                    state.refresh();
                  },
            icon: const Icon(Icons.chevron_left),
          ),
          Text('$page / ${data['pages']}'),
          IconButton(
            tooltip: 'Página siguiente',
            onPressed:
                state.loading || state.busy || page >= (data['pages'] as int)
                ? null
                : () {
                    page++;
                    state.refresh();
                  },
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    ],
  );
}

class OrderDetailScreen extends StatelessWidget {
  const OrderDetailScreen(this.api, this.id, {super.key});
  final ApiClient api;
  final int id;
  Future<void> _act(
    BuildContext context,
    RemotePageState state,
    String action,
  ) async {
    if (state.busy || state.loading) return;
    await state.run(() async {
      String? reason;
      if (action == 'dispute') {
        reason = await askText(
          context,
          'Abrir disputa',
          'Describe lo que ocurrió',
          min: 10,
          max: 500,
        );
        if (reason == null) return;
      } else {
        final explanation = switch (action) {
          'confirm' => 'Confirma únicamente si recibiste el material. Se completará el pedido y se liberará el saldo ficticio al vendedor.',
          'deliver' => 'Indicarás que entregaste el material. El comprador debe confirmar su recepción.',
          'refund' => 'El pago ficticio se devolverá al comprador y el material volverá a estar disponible.',
          _ => 'Resolverás esta operación de demostración. Revisa el historial antes de continuar.',
        };
        if (!await confirmAction(
          context,
          orderActionLabels[action]!,
          '$explanation\n\nSolo simulación: no se mueve dinero real.',
        )) {
          return;
        }
      }
      if (!state.mounted) return;
      await api.post('/api/orders/$id/${action.replaceAll('_', '-')}', {
        'simulation_only': true,
        'reason': ?reason,
      });
    });
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Pedido #$id',
    load: () => api.get('/api/orders/$id'),
    content: (context, data, state) {
      final order = data['order'] as Json;
      final simulated = order['simulated'] == true;
      return [
        if (simulated)
          const PaymentNotice('demo')
        else
          const Text(
            'Esta operación usa un proveedor externo. Su gestión de pagos se realiza desde la web.',
          ),
        const SizedBox(height: 16),
        Text(
          order['post_title'] as String,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
        ),
        Text(
          money(order['amount_cents']),
          style: const TextStyle(fontSize: 24, color: forest),
        ),
        Text(
          orderStatuses[order['status']] ?? 'En revisión',
          key: const Key('order-status'),
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 18),
        Text('Comprador: ${order['buyer']['name']}'),
        Text('Vendedor: ${order['seller']['name']}'),
        Text('Creado: ${dateTimeLabel(order['created_at'])}'),
        if ((order['dispute_reason'] as String? ?? '').isNotEmpty)
          Text('Motivo de disputa: ${order['dispute_reason']}'),
        const SizedBox(height: 16),
        if (order['role'] != 'admin')
          OutlinedButton.icon(
            onPressed: () => state.open(
              ChatScreen(
                api,
                order['post_id'] as int,
                (order['role'] == 'buyer'
                        ? order['seller']['id']
                        : order['buyer']['id'])
                    as int,
              ),
            ),
            icon: const Icon(Icons.chat_outlined),
            label: const Text('Conversar sobre el pedido'),
          ),
        if (simulated) ...[
          for (final action in List<String>.from(order['actions'] as List))
            if (orderActionLabels.containsKey(action))
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: FilledButton(
                  key: Key('order-action-$action'),
                  onPressed: state.busy || state.loading
                      ? null
                      : () => _act(context, state, action),
                  child: Text(orderActionLabels[action]!),
                ),
              ),
        ],
        const Divider(height: 32),
        const Text(
          'Historial',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        for (final event in order['events'] as List? ?? [])
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(event['note'] as String? ?? 'Actualización del pedido'),
            subtitle: Text(
              '${event['actor'] ?? 'Sistema'} · ${dateTimeLabel(event['created_at'])}',
            ),
          ),
      ];
    },
  );
}

class WalletScreen extends StatelessWidget {
  const WalletScreen(this.api, {super.key});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Saldo',
    load: () async => {
      'wallet': await api.get('/api/wallet'),
      'meta': await api.get('/api/meta'),
    },
    content: (context, data, state) {
      final wallet = data['wallet'] as Json;
      return [
        PaymentNotice(data['meta']['payment_mode'] as String),
        const SizedBox(height: 16),
        Text(
          data['meta']['payment_mode'] == 'demo'
              ? 'Saldos ficticios de la demostración. No hay retiros ni transferencias bancarias.'
              : 'Consulta informativa. Gestiona los pagos desde la web.',
        ),
        for (final item in {
          'available_cents': 'Liberado por ventas',
          'pending_cents': 'Pendiente de liberar',
          'buyer_held_cents': 'Retenido por compras',
        }.entries)
          Card(
            child: ListTile(
              title: Text(item.value),
              subtitle: Text(
                money(wallet[item.key]),
                style: const TextStyle(fontSize: 24, color: forest),
              ),
            ),
          ),
      ];
    },
  );
}

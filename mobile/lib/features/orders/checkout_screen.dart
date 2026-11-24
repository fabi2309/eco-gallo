import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../ui/remote_page.dart';
import 'payment_settings_screen.dart';
import 'orders_screen.dart';

class CartScreen extends StatelessWidget {
  const CartScreen(this.api, {super.key});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Carrito',
    load: () => api.get('/api/cart'),
    content: (context, data, state) => [
      if ((data['items'] as List).isEmpty) const Text('Tu carrito está vacío.'),
      for (final item in data['items'] as List)
        Card(
          child: ListTile(
            title: Text('${item['title']}'),
            subtitle: Text(
              '${money(item['price_cents'])} · ${item['seller_name']}\n${item['available'] == true ? 'Disponible' : 'Ya no disponible'}',
            ),
            trailing: IconButton(
              tooltip: 'Quitar del carrito',
              onPressed: state.busy
                  ? null
                  : () => state.run(() async {
                      await api.delete('/api/cart/${item['post_id']}');
                    }),
              icon: const Icon(Icons.remove_shopping_cart_outlined),
            ),
          ),
        ),
      Text('Total disponible: ${money(data['total_cents'])}'),
      FilledButton(
        key: const Key('cart-checkout'),
        onPressed: state.busy || (data['count'] as int) == 0
            ? null
            : () => state.open(CheckoutScreen(api)),
        child: const Text('Continuar compra'),
      ),
    ],
  );
}

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen(this.api, {super.key, this.postId});
  final ApiClient api;
  final int? postId;
  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  String method = 'efectivo', brand = 'visa';
  final holder = TextEditingController(), last4 = TextEditingController();
  final month = TextEditingController(text: '12');
  final year = TextEditingController(text: '${DateTime.now().year + 2}');
  @override
  void dispose() {
    for (final c in [holder, last4, month, year]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Confirmar compra',
    load: () async => {
      'meta': await widget.api.get('/api/meta'),
      'user': await requireCurrentUser(widget.api),
      'purchase': await widget.api.get(
        widget.postId == null ? '/api/cart' : '/api/posts/${widget.postId}',
      ),
    },
    content: (context, data, state) {
      final demo = data['meta']['payment_mode'] == 'demo';
      final ready = data['user']['payments']?['card_ready'] == true;
      final total = widget.postId == null
          ? data['purchase']['total_cents']
          : data['purchase']['post']['price_cents'];
      return [
        Text('Total: ${money(total)}', style: const TextStyle(fontSize: 24)),
        DropdownButtonFormField<String>(
          key: const Key('checkout-method'),
          initialValue: method,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Forma de pago'),
          items: [
            const DropdownMenuItem(
              value: 'efectivo',
              child: Text('Efectivo al entregar'),
            ),
            if (demo)
              const DropdownMenuItem(
                value: 'en_linea',
                child: Text('Tarjeta ficticia · simulación'),
              ),
          ],
          onChanged: state.busy
              ? null
              : (v) => setState(() => method = v ?? method),
        ),
        if (method == 'efectivo')
          const Text(
            'Se apartará el material. El vendedor registrará el cobro al entregar. La plataforma no cobra ni transfiere dinero.',
          )
        else ...[
          const Text(
            'Solo datos ficticios para la tesina. No introduzcas una tarjeta real. No se pide número completo ni CVV.',
          ),
          if (!ready)
            OutlinedButton(
              onPressed: state.busy
                  ? null
                  : () => state.open(PaymentSettingsScreen(widget.api)),
              child: const Text('Confirmar mi teléfono'),
            ),
          DropdownButtonFormField<String>(
            initialValue: brand,
            decoration: const InputDecoration(labelText: 'Marca ficticia'),
            items: [
              'visa',
              'mastercard',
              'amex',
              'carnet',
            ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
            onChanged: state.busy ? null : (v) => brand = v ?? brand,
          ),
          TextField(
            key: const Key('card-holder'),
            controller: holder,
            maxLength: 80,
            decoration: const InputDecoration(labelText: 'Titular ficticio'),
          ),
          TextField(
            key: const Key('card-last4'),
            controller: last4,
            maxLength: 4,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Últimos 4 dígitos ficticios',
            ),
          ),
          TextField(
            controller: month,
            maxLength: 2,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Mes de vencimiento ficticio',
            ),
          ),
          TextField(
            controller: year,
            maxLength: 4,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Año de vencimiento ficticio',
            ),
          ),
        ],
        if (!demo)
          const Text(
            'Los pagos con proveedores externos se gestionan desde la web. Aquí puedes elegir efectivo.',
          ),
        FilledButton(
          key: const Key('confirm-checkout'),
          onPressed:
              state.busy || state.loading || (method == 'en_linea' && !ready)
              ? null
              : () => state.run(() async {
                  if (!await confirmAction(
                    context,
                    'Confirmar compra',
                    method == 'efectivo'
                        ? 'Se reservarán los materiales para pagar al entregar.'
                        : 'Se registrará un pago ficticio. No se mueve dinero real.',
                  )) {
                    return;
                  }
                  final result = await widget.api.post(
                    widget.postId == null
                        ? '/api/cart/checkout'
                        : '/api/orders',
                    {
                      'post_id': ?widget.postId,
                      'method': method,
                      'simulation_only': true,
                      if (method == 'en_linea')
                        'card': {
                          'brand': brand,
                          'last4': last4.text,
                          'holder': holder.text,
                          'exp_month': month.text,
                          'exp_year': year.text,
                        },
                    },
                  );
                  if (!context.mounted) return;
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute<void>(
                      builder: (_) => widget.postId == null
                          ? OrdersScreen(widget.api)
                          : OrderDetailScreen(widget.api, result['id'] as int),
                    ),
                  );
                }),
          child: const Text('Confirmar compra'),
        ),
      ];
    },
  );
}

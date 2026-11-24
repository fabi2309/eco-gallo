import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../models/models.dart';
import '../../ui/remote_page.dart';
import '../../ui/shared.dart';
import '../community/chat_screen.dart';
import '../orders/orders_screen.dart';
import '../orders/checkout_screen.dart';

class DetailScreen extends StatelessWidget {
  const DetailScreen(this.api, this.id, {super.key});
  final ApiClient api;
  final int id;
  Future<Json> _load() async {
    final results = await Future.wait([
      api.get('/api/posts/$id'),
      requireCurrentUser(api),
      api.get('/api/meta'),
    ]);
    return {'post': results[0]['post'], 'user': results[1], 'meta': results[2]};
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Publicación',
    load: _load,
    content: (context, data, state) {
      final raw = data['post'] as Json;
      final p = Post.fromJson(raw);
      final own = p.author.id == data['user']['id'];
      final favorite = raw['is_favorited'] == true;
      final mode = data['meta']['payment_mode'] as String? ?? 'disabled';
      return [
        SizedBox(
          height: 290,
          child: p.images.isEmpty
              ? const Photo(null)
              : PageView(
                  children: [
                    for (final path in p.images)
                      GestureDetector(
                        onTap: () => state.open(
                          Scaffold(
                            appBar: AppBar(title: const Text('Fotografía')),
                            body: Center(
                              child: InteractiveViewer(
                                child: Photo(api.imageUri(path), width: 1400),
                              ),
                            ),
                          ),
                        ),
                        child: Photo(api.imageUri(path), width: 800),
                      ),
                  ],
                ),
        ),
        Wrap(
          spacing: 8,
          children: [
            Chip(label: Text(p.typeLabel)),
            Chip(label: Text(p.category)),
            Chip(label: Text(p.statusLabel)),
          ],
        ),
        if (p.images.length > 1)
          Text('${p.images.length} fotos · Desliza para ver más'),
        const SizedBox(height: 12),
        Text(
          p.title,
          key: const Key('detail-title'),
          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 12),
        Text(
          p.priceLabel,
          style: const TextStyle(
            fontSize: 26,
            color: forest,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 16),
        if (p.status != 'pending' || favorite)
          OutlinedButton.icon(
            key: const Key('toggle-favorite'),
            onPressed: state.busy || state.loading
                ? null
                : () => state.run(() async {
                    await api.post('/api/posts/$id/favorite');
                  }),
            icon: Icon(favorite ? Icons.favorite : Icons.favorite_border),
            label: Text(
              favorite ? 'Quitar de favoritos' : 'Guardar en favoritos',
            ),
          ),
        if (!own && !['pending', 'removed'].contains(p.status))
          FilledButton.icon(
            key: const Key('contact-author'),
            onPressed: () => state.open(ChatScreen(api, id, p.author.id)),
            icon: const Icon(Icons.chat_outlined),
            label: const Text('Contactar'),
          ),
        if (!own && p.status == 'active' && p.tipo == 'venta') ...[
          FilledButton(
            key: Key(mode == 'demo' ? 'buy-demo' : 'buy-cash'),
            onPressed: () => state.open(CheckoutScreen(api, postId: id)),
            child: const Text('Comprar · elegir forma de pago'),
          ),
          OutlinedButton.icon(
            key: const Key('add-cart'),
            onPressed: state.busy
                ? null
                : () => state.run(() async {
                    await api.post('/api/cart', {'post_id': id});
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Agregado al carrito.')),
                      );
                    }
                  }),
            icon: const Icon(Icons.add_shopping_cart),
            label: const Text('Agregar al carrito'),
          ),
        ],
        if (raw['live_order'] != null)
          OutlinedButton(
            onPressed: () => state.open(
              OrderDetailScreen(api, raw['live_order']['id'] as int),
            ),
            child: const Text('Ver pedido en curso'),
          ),
        const SizedBox(height: 20),
        Text(p.description, style: const TextStyle(fontSize: 16, height: 1.5)),
        const SizedBox(height: 20),
        Text('Estado del material: ${p.condition}'),
        if (p.meetPlace.isNotEmpty) Text('Entrega: ${p.meetPlace}'),
        if (p.meetLat != null && p.meetLng != null)
          SelectableText('Ubicación aproximada: ${p.meetLat}, ${p.meetLng}'),
        if (p.newPriceCents > 0)
          Text('Precio nuevo de referencia: ${money(p.newPriceCents)}'),
        if (p.featured) const Text('Publicación destacada'),
        const Divider(height: 32),
        Text(
          p.author.name,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        Text(p.author.carrera),
        Text(p.centro),
        if (!own)
          TextButton.icon(
            onPressed: state.busy
                ? null
                : () => state.run(() async {
                    final reason = await askText(
                      context,
                      'Reportar publicación',
                      'Motivo del reporte',
                      min: 5,
                      max: 400,
                    );
                    if (reason != null && state.mounted) {
                      await api.post('/api/reports', {
                        'target_type': 'post',
                        'target_id': id,
                        'reason': reason,
                      });
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Reporte enviado a revisión.'),
                          ),
                        );
                      }
                    }
                  }),
            icon: const Icon(Icons.flag_outlined),
            label: const Text('Reportar publicación'),
          ),
      ];
    },
  );
}

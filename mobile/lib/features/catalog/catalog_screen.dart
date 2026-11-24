import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../core/session_controller.dart';
import '../../core/photo_picker_service.dart';
import '../posts/my_posts_screen.dart';
import '../posts/post_editor_screen.dart';
import '../../models/models.dart';
import '../../repositories/catalog_repository.dart';
import '../../ui/shared.dart';
import 'detail_screen.dart';
import '../community/community_screens.dart';
import '../community/chat_screen.dart';
import '../orders/orders_screen.dart';
import '../orders/checkout_screen.dart';
import '../orders/payment_settings_screen.dart';
import '../community/legal_screen.dart';

class CatalogScreen extends StatefulWidget {
  const CatalogScreen(this.session, this.picker, {super.key});
  final SessionController session;
  final PhotoPickerService picker;
  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  final search = TextEditingController();
  String category = '', tipo = '';
  String? error;
  bool loading = true, _navigating = false;
  int generation = 0;
  PostPage? data;
  Timer? debounce;
  double? nearbyLat, nearbyLng;
  double nearbyRadius = 10;
  String sort = 'nuevo';
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    debounce?.cancel();
    search.dispose();
    super.dispose();
  }

  Future<void> _load({int page = 1}) async {
    final request = ++generation;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await CatalogRepository(widget.session.api).list(
        query: search.text.trim(),
        category: category,
        tipo: tipo,
        page: page,
        latitude: nearbyLat,
        longitude: nearbyLng,
        radius: nearbyRadius,
        sort: nearbyLat == null ? sort : 'cerca',
      );
      if (!mounted || request != generation) return;
      setState(() {
        data = result;
        loading = false;
      });
    } on ApiException catch (e) {
      if (mounted && request == generation) {
        setState(() {
          error = e.message;
          loading = false;
        });
      }
    }
  }

  Future<void> _openPosts({bool create = false}) async {
    if (_navigating) return;
    _navigating = true;
    try {
      if (create) {
        final saved = await Navigator.push<bool>(
          context,
          MaterialPageRoute(
            builder: (_) => PostEditorScreen(widget.session, widget.picker),
          ),
        );
        if (!mounted || saved != true) return;
      }
      if (!mounted) return;
      await Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (_) => MyPostsScreen(widget.session, widget.picker),
        ),
      );
      if (mounted) _load();
    } finally {
      _navigating = false;
    }
  }

  Future<void> _openCommunity(Widget screen) async {
    if (_navigating) return;
    _navigating = true;
    try {
      Navigator.pop(context);
      await Navigator.push(
        context,
        MaterialPageRoute<void>(builder: (_) => screen),
      );
      if (mounted) _load();
    } finally {
      _navigating = false;
    }
  }

  int _unread(String name) => name == 'Mensajes'
      ? widget.session.unreadMessages
      : name == 'Notificaciones'
      ? widget.session.unreadNotifications
      : 0;

  Future<void> _nearby() async {
    final lat = TextEditingController(text: nearbyLat?.toString());
    final lng = TextEditingController(text: nearbyLng?.toString());
    final radius = TextEditingController(text: '$nearbyRadius');
    String? error;
    final route = DialogRoute<List<double>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          scrollable: true,
          title: const Text('Buscar cerca de un punto'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Coordenadas aproximadas para esta búsqueda. No se guardan en tu perfil.',
              ),
              for (final entry in [
                (lat, 'Latitud'),
                (lng, 'Longitud'),
                (radius, 'Radio en km (hasta 200)'),
              ])
                TextField(
                  controller: entry.$1,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  ),
                  decoration: InputDecoration(labelText: entry.$2),
                ),
              ErrorNotice(error),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () {
                final a = double.tryParse(lat.text),
                    b = double.tryParse(lng.text),
                    c = double.tryParse(radius.text);
                if (a == null ||
                    b == null ||
                    c == null ||
                    !a.isFinite ||
                    !b.isFinite ||
                    !c.isFinite ||
                    a.abs() > 90 ||
                    b.abs() > 180 ||
                    c <= 0 ||
                    c > 200) {
                  update(() => error = 'Revisa las coordenadas y el radio.');
                  return;
                }
                Navigator.pop(context, [a, b, c]);
              },
              child: const Text('Buscar'),
            ),
          ],
        ),
      ),
    );
    final result = await Navigator.of(context).push(route);
    await route.completed;
    lat.dispose();
    lng.dispose();
    radius.dispose();
    if (!mounted || result == null) return;
    setState(() {
      nearbyLat = result[0];
      nearbyLng = result[1];
      nearbyRadius = result[2];
    });
    _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    drawer: Drawer(
      child: SafeArea(
        child: ListView(
          children: [
            const Padding(padding: EdgeInsets.all(20), child: Brand()),
            ListTile(
              title: Text(widget.session.user!.name),
              subtitle: Text(widget.session.user!.email),
            ),
            const Divider(),
            for (final item in <(String, IconData, Widget)>[
              (
                'Carrito',
                Icons.shopping_cart_outlined,
                CartScreen(widget.session.api),
              ),
              (
                'Teléfono y cobros',
                Icons.phone_outlined,
                PaymentSettingsScreen(widget.session.api),
              ),
              (
                'Privacidad y términos',
                Icons.privacy_tip_outlined,
                LegalScreen(widget.session),
              ),
              (
                'Favoritos',
                Icons.favorite_border,
                FavoritesScreen(widget.session.api),
              ),
              (
                'Lista de deseos',
                Icons.playlist_add,
                WishlistScreen(widget.session),
              ),
              (
                'Mensajes',
                Icons.chat_outlined,
                ThreadsScreen(widget.session.api),
              ),
              (
                'Notificaciones',
                Icons.notifications_none,
                NotificationsScreen(widget.session, widget.picker),
              ),
              (
                'Compras y ventas',
                Icons.shopping_bag_outlined,
                OrdersScreen(widget.session.api),
              ),
              (
                'Saldo',
                Icons.account_balance_wallet_outlined,
                WalletScreen(widget.session.api),
              ),
              (
                'Mi perfil',
                Icons.person_outline,
                ProfileScreen(widget.session, widget.picker),
              ),
              (
                'Mi actividad',
                Icons.history,
                ActivityScreen(widget.session, widget.picker),
              ),
              ('Impacto', Icons.eco_outlined, ImpactScreen(widget.session.api)),
            ])
              ListTile(
                key: Key('menu-${item.$1}'),
                leading: Icon(item.$2),
                title: Text(item.$1),
                trailing: _unread(item.$1) > 0
                    ? Badge(
                        label: Text(
                          _unread(item.$1) > 99 ? '99+' : '${_unread(item.$1)}',
                        ),
                      )
                    : null,
                onTap: () => _openCommunity(item.$3),
              ),
          ],
        ),
      ),
    ),
    appBar: AppBar(
      leading: Builder(
        builder: (context) => IconButton(
          key: const Key('open-menu'),
          tooltip: 'Abrir menú',
          icon: Badge(
            isLabelVisible:
                widget.session.unreadMessages +
                    widget.session.unreadNotifications >
                0,
            label: Text(
              widget.session.unreadMessages +
                          widget.session.unreadNotifications >
                      99
                  ? '99+'
                  : '${widget.session.unreadMessages + widget.session.unreadNotifications}',
            ),
            child: const Icon(Icons.menu),
          ),
          onPressed: () => Scaffold.of(context).openDrawer(),
        ),
      ),
      title: const Text(
        'ECO-GALLO',
        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
      ),
      actions: [
        ServerButton(widget.session),
        IconButton(
          tooltip: 'Cerrar sesión',
          onPressed: widget.session.busy ? null : widget.session.logout,
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: Column(
      children: [
        PaymentNotice(widget.session.paymentMode),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => _load(),
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ErrorNotice(widget.session.error),
                        Text(
                          'Hola, ${widget.session.user!.name.split(' ').first}.',
                          style: const TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.w900,
                            color: forest,
                          ),
                        ),
                        const Text(
                          'Dale otra vida a tus materiales.',
                          style: TextStyle(fontSize: 16),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 8,
                          children: [
                            FilledButton.icon(
                              key: const Key('catalog-create'),
                              onPressed: () => _openPosts(create: true),
                              icon: const Icon(Icons.add),
                              label: const Text('Publicar'),
                            ),
                            OutlinedButton.icon(
                              key: const Key('my-posts'),
                              onPressed: _openPosts,
                              icon: const Icon(Icons.inventory_2_outlined),
                              label: const Text('Mis publicaciones'),
                            ),
                            OutlinedButton.icon(
                              onPressed: _nearby,
                              icon: const Icon(Icons.near_me_outlined),
                              label: const Text('Cerca de un punto'),
                            ),
                            if (nearbyLat != null)
                              TextButton(
                                onPressed: () {
                                  setState(() {
                                    nearbyLat = null;
                                    nearbyLng = null;
                                  });
                                  _load();
                                },
                                child: const Text('Quitar cercanía'),
                              ),
                          ],
                        ),
                        const SizedBox(height: 20),
                        TextField(
                          key: const Key('search'),
                          controller: search,
                          decoration: const InputDecoration(
                            hintText: 'Buscar materiales',
                            prefixIcon: Icon(Icons.search),
                          ),
                          onChanged: (_) {
                            debounce?.cancel();
                            debounce = Timer(
                              const Duration(milliseconds: 400),
                              () => _load(),
                            );
                          },
                        ),
                        const SizedBox(height: 12),
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: [
                              for (final c in [
                                '',
                                ...widget.session.categories,
                              ])
                                Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: ChoiceChip(
                                    label: Text(c.isEmpty ? 'Todo' : c),
                                    selected: category == c,
                                    onSelected: (_) {
                                      setState(() => category = c);
                                      _load();
                                    },
                                  ),
                                ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 10),
                        DropdownButtonFormField<String>(
                          initialValue: tipo,
                          decoration: const InputDecoration(
                            labelText: 'Tipo de intercambio',
                          ),
                          items: const [
                            DropdownMenuItem(value: '', child: Text('Todos')),
                            DropdownMenuItem(
                              value: 'venta',
                              child: Text('Venta'),
                            ),
                            DropdownMenuItem(
                              value: 'trueque',
                              child: Text('Trueque'),
                            ),
                            DropdownMenuItem(
                              value: 'donacion',
                              child: Text('Donación'),
                            ),
                          ],
                          onChanged: (v) {
                            setState(() => tipo = v ?? '');
                            _load();
                          },
                        ),
                        const SizedBox(height: 10),
                        DropdownButtonFormField<String>(
                          key: const Key('catalog-sort'),
                          initialValue: sort,
                          isExpanded: true,
                          decoration: InputDecoration(
                            labelText: nearbyLat == null
                                ? 'Ordenar por'
                                : 'Orden por distancia activo',
                          ),
                          items: const [
                            DropdownMenuItem(
                              value: 'nuevo',
                              child: Text('Más recientes'),
                            ),
                            DropdownMenuItem(
                              value: 'barato',
                              child: Text('Menor precio'),
                            ),
                            DropdownMenuItem(
                              value: 'caro',
                              child: Text('Mayor precio'),
                            ),
                          ],
                          onChanged: nearbyLat != null
                              ? null
                              : (value) {
                                  setState(() => sort = value ?? 'nuevo');
                                  _load();
                                },
                        ),
                        const SizedBox(height: 18),
                        Text(
                          '${data?.total ?? 0} publicaciones',
                          key: const Key('result-count'),
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        if (loading)
                          const Padding(
                            padding: EdgeInsets.only(top: 12),
                            child: LinearProgressIndicator(),
                          ),
                        if (error != null) ...[
                          ErrorNotice(error),
                          TextButton(
                            onPressed: () => _load(),
                            child: const Text('Reintentar'),
                          ),
                        ],
                        if (!loading &&
                            error == null &&
                            data?.posts.isEmpty == true)
                          const Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                              'No encontramos publicaciones con esos filtros.',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                if (data != null && error == null)
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    sliver: SliverLayoutBuilder(
                      builder: (context, constraints) => SliverGrid(
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: constraints.crossAxisExtent < 340
                              ? 1
                              : constraints.crossAxisExtent > 650
                              ? 3
                              : 2,
                          mainAxisExtent:
                              290 +
                              (MediaQuery.textScalerOf(context).scale(14) -
                                      14) *
                                  5,
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                        ),
                        delegate: SliverChildBuilderDelegate((context, index) {
                          final post = data!.posts[index];
                          return Card(
                            clipBehavior: Clip.antiAlias,
                            color: Colors.white,
                            margin: EdgeInsets.zero,
                            child: InkWell(
                              key: Key('post-${post.id}'),
                              onTap: () async {
                                if (_navigating) return;
                                _navigating = true;
                                try {
                                  await Navigator.push(
                                    context,
                                    MaterialPageRoute<void>(
                                      builder: (_) => DetailScreen(
                                        widget.session.api,
                                        post.id,
                                      ),
                                    ),
                                  );
                                  if (mounted) {
                                    await _load(page: data?.page ?? 1);
                                  }
                                } finally {
                                  _navigating = false;
                                }
                              },
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  SizedBox(
                                    height: 130,
                                    width: double.infinity,
                                    child: Photo(
                                      widget.session.api.imageUri(
                                        post.images.firstOrNull,
                                      ),
                                      width: 400,
                                    ),
                                  ),
                                  Expanded(
                                    child: Padding(
                                      padding: const EdgeInsets.all(12),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '${post.featured ? '★ ' : ''}${post.typeLabel}${post.distanceKm == null ? '' : ' · ${post.distanceKm!.toStringAsFixed(1)} km'}',
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              color: forest,
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            post.title,
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          const Spacer(),
                                          Text(
                                            post.priceLabel,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w900,
                                              color: forest,
                                              fontSize: 17,
                                            ),
                                          ),
                                          Text(
                                            post.author.name,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              fontSize: 12,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        }, childCount: data!.posts.length),
                      ),
                    ),
                  ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          tooltip: 'Página anterior',
                          onPressed: loading || (data?.page ?? 1) <= 1
                              ? null
                              : () => _load(page: data!.page - 1),
                          icon: const Icon(Icons.chevron_left),
                        ),
                        Text(
                          'Página ${data?.page ?? 1} de ${(data?.pages ?? 0) < 1 ? 1 : data!.pages}',
                        ),
                        IconButton(
                          tooltip: 'Página siguiente',
                          onPressed:
                              loading ||
                                  data == null ||
                                  data!.page >= data!.pages
                              ? null
                              : () => _load(page: data!.page + 1),
                          icon: const Icon(Icons.chevron_right),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

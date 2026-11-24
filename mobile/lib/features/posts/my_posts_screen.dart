import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../core/photo_picker_service.dart';
import '../../core/session_controller.dart';
import '../../models/models.dart';
import '../../repositories/catalog_repository.dart';
import '../../ui/shared.dart';
import '../catalog/detail_screen.dart';
import 'post_editor_screen.dart';
import '../../ui/remote_page.dart';

class MyPostsScreen extends StatefulWidget {
  const MyPostsScreen(this.session, this.picker, {super.key});
  final SessionController session;
  final PhotoPickerService picker;
  @override
  State<MyPostsScreen> createState() => _MyPostsScreenState();
}

class _MyPostsScreenState extends State<MyPostsScreen> {
  PostPage? data;
  String? error;
  bool loading = true, changing = false, navigating = false;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({int? page}) async {
    final current = ++generation;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await CatalogRepository(widget.session.api)
          .list(mine: true, page: page ?? data?.page ?? 1);
      if (mounted && current == generation) {
        setState(() {
          data = result;
          loading = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted && current == generation) {
        setState(() {
          error = e.message;
          loading = false;
        });
      }
    }
  }

  Future<void> _edit([Post? post]) async {
    if (navigating || changing || loading) return;
    navigating = true;
    try {
      final result = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
          builder: (_) =>
              PostEditorScreen(widget.session, widget.picker, post: post),
        ),
      );
      if (!mounted || result != true) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            post == null ? 'Publicación enviada a revisión.' : 'Cambios guardados. El estado se actualizó según las reglas de revisión.',
          ),
        ),
      );
      await _load(page: 1);
    } finally {
      navigating = false;
    }
  }

  Future<void> _pause(Post post) async {
    if (changing || loading) return;
    setState(() {
      changing = true;
      error = null;
    });
    try {
      await CatalogRepository(widget.session.api)
          .pause(post.id, post.status == 'active');
      if (mounted) await _load();
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => changing = false);
    }
  }

  Future<void> _manage(Post post, String action) async {
    if (changing || loading) return;
    setState(() {
      changing = true;
      error = null;
    });
    try {
      if (!await confirmAction(
        context,
        action == 'close' ? 'Marcar como entregado' : 'Retirar publicación',
        action == 'close'
            ? 'El intercambio o donación quedará concluido y dejará de estar disponible.'
            : 'Este material dejará de aparecer en tus publicaciones y en el catálogo.',
      )) {
        return;
      }
      if (!mounted) return;
      if (action == 'close') {
        await widget.session.api.post('/api/posts/${post.id}/close');
      } else {
        await widget.session.api.delete('/api/posts/${post.id}');
      }
      if (mounted) await _load();
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => changing = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Mis publicaciones'),
      actions: [
        IconButton(
          tooltip: 'Actualizar',
          onPressed: loading || changing ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: FloatingActionButton.extended(
      key: const Key('create-post'),
      onPressed: changing ? null : () => _edit(),
      icon: const Icon(Icons.add),
      label: const Text('Publicar'),
    ),
    body: RefreshIndicator(
      onRefresh: () => _load(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const Text(
            'Aquí también aparecen los materiales pendientes de revisión y pausados.',
          ),
          ErrorNotice(error),
          if (loading) const LinearProgressIndicator(),
          if (error != null)
            TextButton(
              onPressed: () => _load(),
              child: const Text('Reintentar'),
            ),
          if (!loading && data?.posts.isEmpty == true)
            const Padding(
              padding: EdgeInsets.all(30),
              child: Text(
                'Todavía no tienes publicaciones. Comparte tu primer material.',
              ),
            ),
          for (final post in data?.posts ?? <Post>[])
            Card(
              key: Key('my-post-${post.id}'),
              margin: const EdgeInsets.symmetric(vertical: 8),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 76,
                          height: 76,
                          child: Photo(
                            widget.session.api.imageUri(
                              post.images.firstOrNull,
                            ),
                            width: 200,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                post.title,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(post.priceLabel),
                              Text(
                                post.statusLabel,
                                key: Key('status-${post.id}'),
                                style: const TextStyle(
                                  color: forest,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 4,
                      children: [
                        if (post.tipo != 'venta' && post.status == 'active')
                          TextButton(
                            onPressed: changing || loading
                                ? null
                                : () => _manage(post, 'close'),
                            child: const Text('Marcar entregado'),
                          ),
                        if (post.status != 'reserved')
                          TextButton(
                            onPressed: changing || loading
                                ? null
                                : () => _manage(post, 'delete'),
                            child: const Text('Retirar'),
                          ),
                        TextButton(
                          onPressed: changing
                              ? null
                              : () async {
                                  if (navigating || loading) return;
                                  navigating = true;
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
                                    if (mounted) _load();
                                  } finally {
                                    navigating = false;
                                  }
                                },
                          child: const Text('Ver detalle'),
                        ),
                        if (post.canEdit)
                          TextButton(
                            key: Key('edit-${post.id}'),
                            onPressed: changing || loading
                                ? null
                                : () => _edit(post),
                            child: const Text('Editar'),
                          ),
                        if (post.status == 'active' || post.status == 'paused')
                          TextButton(
                            key: Key('pause-${post.id}'),
                            onPressed: changing || loading
                                ? null
                                : () => _pause(post),
                            child: Text(
                              post.status == 'active' ? 'Pausar' : 'Reanudar',
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          if (data != null)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  tooltip: 'Página anterior',
                  onPressed: loading || changing || data!.page <= 1
                      ? null
                      : () => _load(page: data!.page - 1),
                  icon: const Icon(Icons.chevron_left),
                ),
                Text('${data!.page} / ${data!.pages}'),
                IconButton(
                  tooltip: 'Página siguiente',
                  onPressed: loading || changing || data!.page >= data!.pages
                      ? null
                      : () => _load(page: data!.page + 1),
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
        ],
      ),
    ),
  );
}

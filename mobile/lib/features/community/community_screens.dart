import 'dart:io';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../core/photo_picker_service.dart';
import '../../core/session_controller.dart';
import '../../models/models.dart';
import '../../ui/remote_page.dart';
import '../../ui/shared.dart';
import '../catalog/detail_screen.dart';
import '../orders/orders_screen.dart';
import '../posts/my_posts_screen.dart';
import 'chat_screen.dart';

Future<void> openCommunityLink(
  BuildContext context,
  ApiClient api,
  String link, {
  SessionController? session,
  PhotoPickerService? picker,
}) async {
  if (!context.mounted || ModalRoute.of(context)?.isCurrent != true) return;
  Widget? page;
  final match = RegExp(r'^#/(post|order|chat)/(\d+)(?:/(\d+))?$')
      .firstMatch(link);
  final id = match == null ? null : int.tryParse(match.group(2)!);
  if (id != null) {
    page = switch (match!.group(1)) {
      'post' => DetailScreen(api, id),
      'order' => OrderDetailScreen(api, id),
      'chat' when int.tryParse(match.group(3) ?? '') != null => ChatScreen(
        api,
        id,
        int.parse(match.group(3)!),
      ),
      _ => null,
    };
  } else if (link == '#/mine' && session != null && picker != null) {
    page = MyPostsScreen(session, picker);
  }
  if (page != null) {
    await Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => page!),
    );
  } else if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Esta sección se consulta desde la web.')),
    );
  }
}

class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen(this.api, {super.key});
  final ApiClient api;
  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  int page = 1;
  Future<Json> _load() async {
    final ids = List<int>.from(
      (await widget.api.get('/api/favorites'))['post_ids'] as List,
    );
    final pages = ((ids.length + 19) ~/ 20).clamp(1, 1000000);
    page = page.clamp(1, pages);
    final current = ids.skip((page - 1) * 20).take(20).toList();
    final items = <Json>[];
    for (var offset = 0; offset < current.length; offset += 5) {
      items.addAll(
        await Future.wait(
          current.skip(offset).take(5).map((id) async {
            try {
              return {
                'id': id,
                'post': (await widget.api.get('/api/posts/$id'))['post'],
              };
            } on ApiException catch (e) {
              if (e.status == 404) return {'id': id, 'post': null};
              rethrow;
            }
          }),
        ),
      );
    }
    return {'items': items, 'pages': pages};
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Favoritos',
    load: _load,
    content: (context, data, state) => [
      if ((data['items'] as List).isEmpty)
        const Text(
          'Guarda materiales con el corazón de su pantalla de detalle.',
        ),
      for (final item in data['items'] as List)
        Card(
          child: ListTile(
            key: Key('favorite-${item['id']}'),
            title: Text(
              item['post']?['title'] as String? ?? 'Material no disponible',
            ),
            subtitle: item['post'] == null
                ? const Text('Puedes quitarlo de tus favoritos.')
                : Text(Post.fromJson(item['post'] as Json).priceLabel),
            onTap: item['post'] == null
                ? null
                : () => state.open(DetailScreen(widget.api, item['id'] as int)),
            trailing: IconButton(
              tooltip: 'Quitar de favoritos',
              onPressed: state.busy || state.loading
                  ? null
                  : () => state.run(() async {
                      await widget.api.post(
                        '/api/posts/${item['id']}/favorite',
                      );
                    }),
              icon: const Icon(Icons.favorite, color: forest),
            ),
          ),
        ),
      Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(
            tooltip: 'Página anterior',
            onPressed: state.busy || state.loading || page <= 1
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
                state.busy || state.loading || page >= (data['pages'] as int)
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

class WishlistScreen extends StatefulWidget {
  const WishlistScreen(this.session, {super.key});
  final SessionController session;
  @override
  State<WishlistScreen> createState() => _WishlistScreenState();
}

class _WishlistScreenState extends State<WishlistScreen> {
  final term = TextEditingController();
  final form = GlobalKey<FormState>();
  String category = '', centro = '';
  @override
  void dispose() {
    term.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Lista de deseos',
    load: () => widget.session.api.get('/api/wishlist'),
    content: (context, data, state) => [
      const Text(
        'Recibe un aviso cuando se apruebe un material que coincida con lo que buscas.',
      ),
      const SizedBox(height: 16),
      Form(
        key: form,
        child: Column(
          children: [
            TextFormField(
              key: const Key('wish-term'),
              controller: term,
              maxLength: 60,
              enabled: !state.busy,
              decoration: const InputDecoration(
                labelText: '¿Qué estás buscando?',
              ),
              validator: (v) => (v?.trim().length ?? 0) < 2
                  ? 'Escribe al menos 2 caracteres.'
                  : null,
            ),
            DropdownButtonFormField<String>(
              initialValue: category,
              decoration: const InputDecoration(labelText: 'Categoría'),
              isExpanded: true,
              items: ['', ...widget.session.categories]
                  .map(
                    (v) => DropdownMenuItem(
                      value: v,
                      child: Text(v.isEmpty ? 'Cualquier categoría' : v),
                    ),
                  )
                  .toList(),
              onChanged: state.busy ? null : (v) => category = v ?? '',
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: centro,
              decoration: const InputDecoration(labelText: 'Centro académico'),
              isExpanded: true,
              items:
                  [
                        '',
                        ...List<String>.from(
                          widget.session.meta['centros'] as List? ?? [],
                        ),
                      ]
                      .map(
                        (v) => DropdownMenuItem(
                          value: v,
                          child: Text(
                            v.isEmpty ? 'Cualquier centro' : v,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
              onChanged: state.busy ? null : (v) => centro = v ?? '',
            ),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('add-wish'),
              onPressed:
                  state.busy ||
                      state.loading ||
                      (data['items'] as List).length >= (data['max'] as int)
                  ? null
                  : () {
                      if (!form.currentState!.validate()) return;
                      state.run(() async {
                        await widget.session.api.post('/api/wishlist', {
                          'term': term.text.trim(),
                          'category': category,
                          'centro': centro,
                        });
                        term.clear();
                      });
                    },
              child: const Text('Agregar deseo'),
            ),
          ],
        ),
      ),
      const SizedBox(height: 20),
      Text('${(data['items'] as List).length} / ${data['max']} deseos'),
      for (final item in data['items'] as List)
        Card(
          child: ListTile(
            title: Text(item['term'] as String),
            subtitle: Text(
              [
                item['category'],
                item['centro'],
              ].where((v) => v != '').join(' · '),
            ),
            trailing: IconButton(
              tooltip: 'Quitar deseo',
              onPressed: state.busy
                  ? null
                  : () => state.run(() async {
                      await widget.session.api.delete(
                        '/api/wishlist/${item['id']}',
                      );
                    }),
              icon: const Icon(Icons.delete_outline),
            ),
          ),
        ),
    ],
  );
}

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen(this.session, this.picker, {super.key});
  final SessionController session;
  final PhotoPickerService picker;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Notificaciones',
    refreshInterval: const Duration(seconds: 15),
    load: () => session.api.get('/api/notifications'),
    content: (context, data, state) => [
      if ((data['notifications'] as List).isEmpty)
        const Text('No tienes notificaciones.'),
      if ((data['notifications'] as List).any((n) => n['read_at'] == null))
        OutlinedButton(
          key: const Key('read-notifications'),
          onPressed: state.busy
              ? null
              : () => state.run(() async {
                  await session.api.post('/api/notifications/read', {
                    'ids': [
                      for (final note in data['notifications'] as List)
                        if (note['read_at'] == null) note['id'],
                    ],
                  });
                }),
          child: const Text('Marcar estas como leídas'),
        ),
      for (final note in data['notifications'] as List)
        Card(
          child: ListTile(
            leading: Icon(
              note['read_at'] == null
                  ? Icons.notifications_active_outlined
                  : Icons.notifications_none,
            ),
            title: Text(
              note['text'] as String,
              style: TextStyle(
                fontWeight: note['read_at'] == null
                    ? FontWeight.bold
                    : FontWeight.normal,
              ),
            ),
            subtitle: Text(dateTimeLabel(note['created_at'])),
            onTap: state.busy || state.loading
                ? null
                : () => state.run(() async {
                    if (note['read_at'] == null) {
                      await session.api.post('/api/notifications/read', {
                        'ids': [note['id']],
                      });
                    }
                    if (!context.mounted) return;
                    await openCommunityLink(
                      context,
                      session.api,
                      note['link'] as String? ?? '',
                      session: session,
                      picker: picker,
                    );
                  }),
          ),
        ),
    ],
  );
}

class ActivityScreen extends StatefulWidget {
  const ActivityScreen(this.session, this.picker, {super.key});
  final SessionController session;
  final PhotoPickerService picker;
  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen> {
  String kind = 'todo';
  int page = 1;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Mi actividad',
    load: () => widget.session.api.get('/api/activity', {
      'kind': kind,
      'page': '$page',
    }),
    content: (context, data, state) => [
      DropdownButtonFormField<String>(
        initialValue: kind,
        decoration: const InputDecoration(labelText: 'Mostrar'),
        items:
            const {
                  'todo': 'Todo',
                  'publicaciones': 'Publicaciones',
                  'compras': 'Compras',
                  'ventas': 'Ventas',
                  'mensajes': 'Mensajes',
                }.entries
                .map(
                  (e) => DropdownMenuItem(value: e.key, child: Text(e.value)),
                )
                .toList(),
        onChanged: state.loading || state.busy
            ? null
            : (v) {
                kind = v ?? 'todo';
                page = 1;
                state.refresh();
              },
      ),
      if ((data['items'] as List).isEmpty)
        const Padding(
          padding: EdgeInsets.all(24),
          child: Text('Aún no hay actividad en esta categoría.'),
        ),
      for (final item in data['items'] as List)
        ListTile(
          title: Text(item['title'] as String),
          subtitle: Text(
            '${item['detail'] ?? ''}\n${dateTimeLabel(item['ts'])}',
          ),
          onTap: () => openCommunityLink(
            context,
            widget.session.api,
            item['link'] as String,
            session: widget.session,
            picker: widget.picker,
          ),
        ),
      Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(
            tooltip: 'Página anterior',
            onPressed: state.loading || page <= 1
                ? null
                : () {
                    page--;
                    state.refresh();
                  },
            icon: const Icon(Icons.chevron_left),
          ),
          Text('${data['page']} / ${data['pages']}'),
          IconButton(
            tooltip: 'Página siguiente',
            onPressed: state.loading || page >= (data['pages'] as int)
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

class ImpactScreen extends StatelessWidget {
  const ImpactScreen(this.api, {super.key});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Impacto de la comunidad',
    load: () => api.get('/api/impact'),
    content: (context, data, state) => [
      for (final entry in {
        'users': 'Personas en la comunidad',
        'active_posts': 'Materiales disponibles o reservados',
        'reused_items': 'Materiales reutilizados',
        'co2_kg': 'kg de CO₂e estimados',
      }.entries)
        Card(
          child: ListTile(
            title: Text(entry.value),
            trailing: Text(
              '${data[entry.key]}',
              style: const TextStyle(fontSize: 24, color: forest),
            ),
          ),
        ),
      Text(
        data['co2_note'] as String? ??
            'Estimación orientativa, no una medición.',
      ),
      const SizedBox(height: 16),
      const Text(
        'Publicaciones por categoría',
        style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
      ),
      for (final entry in (data['posts_by_category'] as Json).entries)
        ListTile(title: Text(entry.key), trailing: Text('${entry.value}')),
    ],
  );
}

class ProfileScreen extends StatefulWidget {
  const ProfileScreen(this.session, this.picker, {super.key});
  final SessionController session;
  final PhotoPickerService picker;
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final name = TextEditingController(), bio = TextEditingController();
  final form = GlobalKey<FormState>();
  bool initialized = false;
  String? career;
  @override
  void dispose() {
    name.dispose();
    bio.dispose();
    super.dispose();
  }

  Future<void> _avatar() async {
    try {
      final files = await widget.picker.pick(limit: 1);
      if (!mounted || files.isEmpty) return;
      await validatePhotos(files, maxCount: 1, maxBytes: 2 * 1024 * 1024);
      await widget.session.api.multipart('POST', '/api/me/avatar', {}, [
        await http.MultipartFile.fromPath(
          'avatar',
          files.single.path,
          filename: 'perfil.jpg',
        ),
      ]);
    } on PlatformException {
      throw const ApiException(
        'No pudimos abrir las fotos. Inténtalo nuevamente.',
      );
    } on FileSystemException {
      throw const ApiException(
        'No pudimos leer la foto. Selecciónala nuevamente.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Mi perfil',
    load: () async => {'user': await requireCurrentUser(widget.session.api)},
    content: (context, data, state) {
      final user = data['user'] as Json;
      if (!initialized) {
        initialized = true;
        name.text = user['name'] as String;
        bio.text = user['bio'] as String? ?? '';
        career = user['carrera'] as String;
      }
      return [
        SizedBox(
          height: 120,
          child: Photo(widget.session.api.imageUri(user['avatar'] as String?)),
        ),
        Wrap(
          spacing: 8,
          children: [
            TextButton.icon(
              onPressed: state.busy || state.loading
                  ? null
                  : () => state.run(_avatar),
              icon: const Icon(Icons.photo_camera_outlined),
              label: const Text('Cambiar foto'),
            ),
            if ((user['avatar'] as String? ?? '').isNotEmpty)
              TextButton(
                onPressed: state.busy
                    ? null
                    : () => state.run(() async {
                        if (await confirmAction(
                          context,
                          'Quitar foto',
                          'Tu perfil dejará de mostrar esta foto.',
                        )) {
                          await widget.session.api.delete('/api/me/avatar');
                        }
                      }),
                child: const Text('Quitar foto'),
              ),
          ],
        ),
        Text(user['email'] as String),
        const SizedBox(height: 16),
        Form(
          key: form,
          child: Column(
            children: [
              TextFormField(
                key: const Key('edit-profile-name'),
                controller: name,
                enabled: !state.busy,
                maxLength: 80,
                decoration: const InputDecoration(labelText: 'Nombre'),
                validator: (v) => (v?.trim().length ?? 0) < 3
                    ? 'Escribe al menos 3 caracteres.'
                    : null,
              ),
              DropdownButtonFormField<String>(
                initialValue: widget.session.carreras.contains(career)
                    ? career
                    : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Carrera'),
                items: widget.session.carreras
                    .map(
                      (v) => DropdownMenuItem(
                        value: v,
                        child: Text(v, overflow: TextOverflow.ellipsis),
                      ),
                    )
                    .toList(),
                onChanged: state.busy ? null : (v) => career = v,
                validator: (v) => v == null ? 'Elige tu carrera.' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                key: const Key('edit-profile-bio'),
                controller: bio,
                enabled: !state.busy,
                maxLength: 200,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Acerca de ti'),
              ),
              FilledButton(
                key: const Key('save-profile'),
                onPressed: state.busy || state.loading
                    ? null
                    : () {
                        if (!form.currentState!.validate()) return;
                        state.run(() async {
                          await widget.session.api.put('/api/me', {
                            'name': name.text.trim(),
                            'carrera': career,
                            'bio': bio.text.trim(),
                          });
                          await widget.session.refreshSession();
                        });
                      },
                child: const Text('Guardar perfil'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Text('Centro: ${user['centro']}'),
        Text(
          'Segundo factor: ${user['totp_enabled'] == true ? 'activado' : 'sin activar'}',
        ),
        const Text(
          'La contraseña, la configuración del segundo factor y la verificación de egresados se gestionan desde la web.',
        ),
      ];
    },
  );
}

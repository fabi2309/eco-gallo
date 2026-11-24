import 'dart:io';

import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../core/photo_picker_service.dart';
import '../../core/session_controller.dart';
import '../../models/models.dart';
import '../../repositories/catalog_repository.dart';
import '../../ui/shared.dart';

class PostEditorScreen extends StatefulWidget {
  const PostEditorScreen(this.session, this.picker, {super.key, this.post});
  final SessionController session;
  final PhotoPickerService picker;
  final Post? post;
  @override
  State<PostEditorScreen> createState() => _PostEditorScreenState();
}

class _PostEditorScreenState extends State<PostEditorScreen> {
  final form = GlobalKey<FormState>();
  late final title = TextEditingController(text: widget.post?.title);
  late final description = TextEditingController(
    text: widget.post?.description,
  );
  late final price = TextEditingController(
    text: widget.post == null
        ? ''
        : (widget.post!.priceCents / 100).toStringAsFixed(2),
  );
  late String tipo = widget.post?.tipo ?? 'venta';
  late String condition = widget.post?.condition ?? 'Usado';
  late String centro =
      widget.post?.centro ?? widget.session.user?.centro ?? 'General';
  String? category;
  final photos = <XFile>[];
  String? error, notice;
  bool busy = false, picking = false, dirty = false, saved = false;
  bool _leaving = false;
  int get maxPhotos =>
      (widget.session.meta['max_images'] as int? ?? 5).clamp(1, 5);
  int get maxBytes =>
      (widget.session.meta['max_image_bytes'] as int? ?? 5 * 1024 * 1024).clamp(
        1,
        5 * 1024 * 1024,
      );
  List<String> options(String key) =>
      List<String>.from(widget.session.meta[key] as List? ?? []);
  @override
  void initState() {
    super.initState();
    category = widget.post?.category;
    widget.session.addListener(_sessionChanged);
    for (final controller in [title, description, price]) {
      final original = controller.text;
      controller.addListener(() {
        if (!dirty && mounted && controller.text != original) {
          setState(() => dirty = true);
        }
      });
    }
    if (widget.post == null) _recover();
  }

  void _sessionChanged() {
    if (mounted && widget.session.phase != SessionPhase.signedIn) {
      setState(() => saved = true);
    }
  }

  Future<void> _recover() async {
    final recovered = await widget.picker.takeRecovered();
    if (!mounted || recovered.isEmpty) return;
    await _accept(recovered, recovered: true);
  }

  Future<void> _accept(List<XFile> selected, {bool recovered = false}) async {
    try {
      await validatePhotos(
        [...photos, ...selected],
        maxCount: maxPhotos,
        maxBytes: maxBytes,
      );
      if (!mounted) return;
      setState(() {
        photos.addAll(selected);
        dirty = true;
        error = null;
        if (recovered) notice = 'Recuperamos las fotos de tu selección anterior. Completa los datos antes de enviar.';
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } on FileSystemException {
      if (mounted) {
        setState(
          () => error = 'No pudimos leer una foto. Selecciónala nuevamente.',
        );
      }
    }
  }

  Future<void> _pick() async {
    if (busy || picking || photos.length >= maxPhotos) return;
    setState(() {
      picking = true;
      error = null;
    });
    try {
      final selected = await widget.picker.pick(
        limit: maxPhotos - photos.length,
      );
      if (mounted && selected.isNotEmpty) await _accept(selected);
    } on PlatformException {
      if (mounted) {
        setState(
          () => error = 'No pudimos abrir las fotos. Revisa el acceso a la galería e intenta de nuevo.',
        );
      }
    } on MissingPluginException {
      if (mounted) {
        setState(
          () => error = 'Reinicia la app para activar el selector de fotos.',
        );
      }
    } finally {
      if (mounted) setState(() => picking = false);
    }
  }

  Future<void> _submit() async {
    if (busy || picking) return;
    FocusManager.instance.primaryFocus?.unfocus();
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await validatePhotos(photos, maxCount: maxPhotos, maxBytes: maxBytes);
      await CatalogRepository(widget.session.api).save(
        {
          'title': title.text.trim(),
          'description': description.text.trim(),
          'category': category!,
          'centro': centro,
          'tipo': tipo,
          'condition': condition,
          'price': tipo == 'venta'
              ? price.text.trim().replaceAll(',', '.')
              : '0',
        },
        photos,
        id: widget.post?.id,
      );
      if (!mounted) return;
      setState(() {
        saved = true;
        busy = false;
      });
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } on FileSystemException {
      if (mounted) {
        setState(
          () =>
              error = 'Una foto ya no está disponible. Vuelve a seleccionarla.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _leave() async {
    if (busy || picking || _leaving) return;
    _leaving = true;
    if (!dirty) {
      Navigator.pop(context);
      return;
    }
    final discard = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: const Text('¿Salir sin guardar?'),
        content: const Text(
          'Se perderán los datos y las fotos seleccionadas de este formulario.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Continuar editando'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Salir sin guardar'),
          ),
        ],
      ),
    );
    if (discard != true) _leaving = false;
    if (discard == true && mounted) {
      setState(() => saved = true);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.pop(context);
      });
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(_sessionChanged);
    title.dispose();
    description.dispose();
    price.dispose();
    super.dispose();
  }

  Widget dropdown(
    String label,
    String key,
    String? value,
    List<String> values,
    ValueChanged<String> change,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: DropdownButtonFormField<String>(
      key: Key(key),
      initialValue: values.contains(value) ? value : null,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: values
          .map(
            (v) => DropdownMenuItem(
              value: v,
              child: Text(
                v == 'venta'
                    ? 'Venta'
                    : v == 'trueque'
                    ? 'Trueque'
                    : v == 'donacion'
                    ? 'Donación'
                    : v,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          )
          .toList(),
      onChanged: busy || picking
          ? null
          : (v) {
              if (v != null) {
                setState(() {
                  change(v);
                  dirty = true;
                });
              }
            },
      validator: (v) => v == null ? 'Elige una opción.' : null,
    ),
  );
  @override
  Widget build(BuildContext context) => PopScope(
    canPop: saved || (!dirty && !busy && !picking),
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop) _leave();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(
          widget.post == null ? 'Publicar material' : 'Editar publicación',
        ),
        leading: IconButton(
          tooltip: 'Volver',
          onPressed: busy || picking ? null : _leave,
          icon: const Icon(Icons.arrow_back),
        ),
      ),
      body: SafeArea(
        child: Form(
          key: form,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Dale una nueva historia',
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w900,
                    color: forest,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Las publicaciones nuevas y los cambios de contenido o fotos pasan por revisión antes de aparecer en el catálogo.',
                ),
                if (notice != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(notice!),
                  ),
                const SizedBox(height: 20),
                TextFormField(
                  key: const Key('post-title'),
                  controller: title,
                  enabled: !busy && !picking,
                  maxLength: 100,
                  decoration: const InputDecoration(labelText: 'Título'),
                  validator: (v) => (v?.trim().length ?? 0) < 3
                      ? 'Escribe al menos 3 caracteres.'
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  key: const Key('post-description'),
                  controller: description,
                  enabled: !busy && !picking,
                  minLines: 3,
                  maxLines: 6,
                  maxLength: 1500,
                  decoration: const InputDecoration(
                    labelText: 'Descripción y condición del material',
                  ),
                  validator: (v) => (v?.trim().length ?? 0) < 10
                      ? 'Escribe al menos 10 caracteres.'
                      : null,
                ),
                const SizedBox(height: 12),
                dropdown(
                  'Categoría',
                  'post-category',
                  category,
                  widget.session.categories,
                  (v) => category = v,
                ),
                dropdown(
                  'Tipo de intercambio',
                  'post-type',
                  tipo,
                  options('tipos'),
                  (v) => tipo = v,
                ),
                if (tipo == 'venta') ...[
                  TextFormField(
                    key: const Key('post-price'),
                    controller: price,
                    enabled: !busy && !picking,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: const InputDecoration(
                      labelText: 'Precio en MXN',
                      prefixText: '\$ ',
                    ),
                    validator: (v) {
                      final text = v?.trim().replaceAll(',', '.') ?? '';
                      if (!RegExp(r'^\d{1,5}(\.\d{1,2})?$').hasMatch(text)) {
                        return 'Escribe un precio con hasta 2 decimales.';
                      }
                      final amount = double.tryParse(text) ?? 0;
                      final max =
                          (widget.session.meta['max_price_cents'] as int? ??
                              1000000) /
                          100;
                      return amount <= 0 || amount > max
                          ? 'El precio debe ser mayor a 0 y hasta \$$max MXN.'
                          : null;
                    },
                  ),
                  const SizedBox(height: 16),
                ],
                dropdown(
                  'Estado del material',
                  'post-condition',
                  condition,
                  options('conditions'),
                  (v) => condition = v,
                ),
                dropdown(
                  'Centro académico',
                  'post-centro',
                  centro,
                  options('centros'),
                  (v) => centro = v,
                ),
                Text(
                  'Fotografías · ${photos.length}/$maxPhotos seleccionadas',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const Text(
                  'JPG, PNG o WebP; hasta 5 MB por foto. Las fotos son opcionales.',
                ),
                if (widget.post?.images.isNotEmpty == true &&
                    photos.isEmpty) ...[
                  const SizedBox(height: 8),
                  const Text('Se conservarán tus fotos actuales.'),
                  SizedBox(
                    height: 90,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        for (final image in widget.post!.images)
                          Padding(
                            padding: const EdgeInsets.all(4),
                            child: SizedBox(
                              width: 90,
                              child: Photo(
                                widget.session.api.imageUri(image),
                                width: 240,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
                if (widget.post != null && photos.isNotEmpty)
                  const Text(
                    'Al guardar, estas fotos reemplazarán todas las anteriores.',
                  ),
                if (photos.isNotEmpty)
                  SizedBox(
                    height: 140,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        for (var i = 0; i < photos.length; i++)
                          SizedBox(
                            width: 120,
                            child: Padding(
                              padding: const EdgeInsets.all(4),
                              child: Column(
                                children: [
                                  Expanded(
                                    child: Image.file(
                                      File(photos[i].path),
                                      width: 110,
                                      cacheWidth: 240,
                                      fit: BoxFit.cover,
                                      errorBuilder: (_, _, _) => const Icon(
                                        Icons.broken_image_outlined,
                                      ),
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Quitar foto ${i + 1}',
                                    onPressed: busy || picking
                                        ? null
                                        : () => setState(() {
                                            photos.removeAt(i);
                                            dirty = true;
                                          }),
                                    icon: const Icon(Icons.close),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                OutlinedButton.icon(
                  key: const Key('pick-photos'),
                  onPressed: busy || picking || photos.length >= maxPhotos
                      ? null
                      : _pick,
                  icon: const Icon(Icons.add_photo_alternate_outlined),
                  label: Text(
                    picking ? 'Abriendo fotos…' : 'Seleccionar fotos',
                  ),
                ),
                ErrorNotice(error),
                const SizedBox(height: 20),
                FilledButton(
                  key: const Key('save-post'),
                  onPressed: busy || picking ? null : _submit,
                  child: busy
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(
                          widget.post == null
                              ? 'Enviar a revisión'
                              : 'Guardar cambios',
                        ),
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

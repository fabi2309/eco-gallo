import 'package:material_ui/material_ui.dart';

import 'dart:async';

import '../core/api_client.dart';
import 'shared.dart';

typedef Json = Map<String, dynamic>;

Future<Json> requireCurrentUser(ApiClient api) async {
  final me = await api.get('/api/me');
  if (me['user'] is Json) return me['user'] as Json;
  api.clearSession();
  api.onSessionExpired?.call();
  throw const ApiException('Tu sesión venció. Vuelve a entrar.', status: 401);
}

String money(dynamic cents) =>
    '\$${((cents as num? ?? 0) / 100).toStringAsFixed(2)} MXN';
String dateTimeLabel(dynamic seconds) {
  if (seconds is! num) return '';
  final date = DateTime.fromMillisecondsSinceEpoch(seconds.toInt() * 1000)
      .toLocal();
  String pad(int n) => '$n'.padLeft(2, '0');
  return '${pad(date.day)}/${pad(date.month)}/${date.year} ${pad(date.hour)}:${pad(date.minute)}';
}

class RemotePage extends StatefulWidget {
  const RemotePage({
    super.key,
    required this.title,
    required this.load,
    required this.content,
    this.refreshInterval,
  });
  final String title;
  final Future<Json> Function() load;
  final Duration? refreshInterval;
  final List<Widget> Function(BuildContext, Json, RemotePageState) content;
  @override
  State<RemotePage> createState() => RemotePageState();
}

class RemotePageState extends State<RemotePage> with WidgetsBindingObserver {
  Json? data;
  String? error;
  bool loading = true, busy = false;
  int generation = 0;
  int _requests = 0;
  Timer? _timer;
  bool _foreground = true;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _foreground =
        WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    if (widget.refreshInterval != null) {
      _timer = Timer.periodic(widget.refreshInterval!, (_) => _poll());
    }
    refresh();
  }

  void _poll() {
    if (mounted &&
        _foreground &&
        !busy &&
        !loading &&
        _requests == 0 &&
        ModalRoute.of(context)?.isCurrent == true) {
      refresh(quiet: data != null);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground && widget.refreshInterval != null) _poll();
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> refresh({bool quiet = false}) async {
    if (!mounted) return;
    _requests++;
    final current = ++generation;
    setState(() {
      loading = !quiet;
      error = null;
    });
    try {
      final result = await widget.load();
      if (mounted && current == generation) setState(() => data = result);
    } on ApiException catch (e) {
      if (mounted && current == generation) setState(() => error = e.message);
    } finally {
      _requests--;
      if (mounted && current == generation) setState(() => loading = false);
    }
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy || loading) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
      if (mounted) await refresh();
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> open(Widget screen) => run(() async {
    await Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.title),
      actions: [
        IconButton(
          tooltip: 'Actualizar',
          onPressed: loading || busy ? null : refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: busy ? () async {} : refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          if ((loading || busy) && ModalRoute.of(context)?.isCurrent != false)
            const LinearProgressIndicator(),
          ErrorNotice(error),
          if (error != null)
            TextButton(onPressed: refresh, child: const Text('Reintentar')),
          if (data != null) ...widget.content(context, data!, this),
          const SizedBox(height: 30),
        ],
      ),
    ),
  );
}

Future<bool> confirmAction(
  BuildContext context,
  String title,
  String explanation,
) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: Text(title),
        content: Text(explanation),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    ) ??
    false;

Future<String?> askText(
  BuildContext context,
  String title,
  String label, {
  int min = 1,
  int max = 400,
}) async {
  final controller = TextEditingController();
  final form = GlobalKey<FormState>();
  final route = DialogRoute<String>(
    context: context,
    builder: (context) => AlertDialog(
      scrollable: true,
      title: Text(title),
      content: Form(
        key: form,
        child: TextFormField(
          key: const Key('action-reason'),
          controller: controller,
          autofocus: true,
          minLines: 2,
          maxLines: 5,
          maxLength: max,
          decoration: InputDecoration(labelText: label),
          validator: (value) => (value?.trim().length ?? 0) < min
              ? 'Escribe al menos $min caracteres.'
              : null,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: () {
            if (form.currentState!.validate()) {
              Navigator.pop(context, controller.text.trim());
            }
          },
          child: const Text('Continuar'),
        ),
      ],
    ),
  );
  final result = await Navigator.of(context).push(route);
  await route.completed;
  controller.dispose();
  return result;
}

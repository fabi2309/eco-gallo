import 'dart:async';
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../../core/api_client.dart';
import '../../ui/remote_page.dart';
import '../../ui/shared.dart';

class ThreadsScreen extends StatelessWidget {
  const ThreadsScreen(this.api, {super.key});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => RemotePage(
    title: 'Mensajes',
    refreshInterval: const Duration(seconds: 15),
    load: () => api.get('/api/threads'),
    content: (context, data, state) => [
      if ((data['threads'] as List).isEmpty)
        const Text(
          'Aún no tienes conversaciones. Abre un material y pulsa Contactar.',
        ),
      for (final thread in data['threads'] as List)
        Card(
          child: ListTile(
            key: Key('thread-${thread['post_id']}-${thread['other']['id']}'),
            title: Text('${thread['other']['name']} · ${thread['post_title']}'),
            subtitle: Text(
              '${thread['last']['content']}\n${dateTimeLabel(thread['last']['created_at'])}',
            ),
            trailing: (thread['unread'] as int) > 0
                ? Badge(label: Text('${thread['unread']}'))
                : null,
            onTap: () => state.open(
              ChatScreen(
                api,
                thread['post_id'] as int,
                thread['other']['id'] as int,
              ),
            ),
          ),
        ),
    ],
  );
}

class ChatScreen extends StatefulWidget {
  const ChatScreen(this.api, this.postId, this.otherId, {super.key});
  final ApiClient api;
  final int postId, otherId;
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  final text = TextEditingController();
  final scroll = ScrollController();
  Json? data;
  int? userId;
  bool loading = false, sending = false, foreground = true;
  String? error;
  Timer? timer;
  Future<void>? _inflight;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
    timer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (mounted &&
          foreground &&
          ModalRoute.of(context)?.isCurrent == true &&
          !sending) {
        _load();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground && mounted && ModalRoute.of(context)?.isCurrent == true) {
      _load();
    }
  }

  Future<void> _load({bool latest = false}) {
    if (!mounted) return Future.value();
    return _inflight ??= _fetch(latest: latest)
        .whenComplete(() => _inflight = null);
  }

  Future<void> _fetch({bool latest = false}) async {
    final atBottom =
        latest ||
        !scroll.hasClients ||
        scroll.position.maxScrollExtent - scroll.offset < 100;
    setState(() => loading = true);
    try {
      userId ??= (await requireCurrentUser(widget.api))['id'] as int;
      final result = await widget.api.get(
        '/api/threads/${widget.postId}/${widget.otherId}',
      );
      if (!mounted) return;
      setState(() {
        data = result;
        error = null;
      });
      if (atBottom) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && scroll.hasClients) {
            scroll.jumpTo(scroll.position.maxScrollExtent);
          }
        });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _send() async {
    final message = text.text.trim();
    if (sending || message.isEmpty) return;
    setState(() {
      sending = true;
      error = null;
    });
    try {
      await widget.api.post('/api/messages', {
        'post_id': widget.postId,
        'receiver_id': widget.otherId,
        'content': message,
      });
      if (!mounted) return;
      text.clear();
      if (_inflight != null) await _inflight;
      if (mounted) await _load(latest: true);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    text.dispose();
    scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final messages = data?['messages'] as List? ?? [];
    final compact =
        MediaQuery.viewInsetsOf(context).bottom > 0 ||
        MediaQuery.sizeOf(context).height < 500 ||
        MediaQuery.textScalerOf(context).scale(14) > 20;
    return Scaffold(
      appBar: AppBar(
        title: Text(data?['other']['name'] as String? ?? 'Conversación'),
        actions: [
          IconButton(
            tooltip: 'Actualizar',
            onPressed: loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final height = math.max(
              constraints.maxHeight,
              (compact ? 210.0 : 320.0) +
                  MediaQuery.textScalerOf(context).scale(24),
            );
            return SingleChildScrollView(
              child: SizedBox(
                height: height,
                child: Column(
                  children: [
                    if (data != null && !compact)
                      Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(
                          data!['post']['title'] as String,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                    if (loading && data == null)
                      const LinearProgressIndicator(),
                    if (error != null)
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 90),
                        child: SingleChildScrollView(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            child: ErrorNotice(error),
                          ),
                        ),
                      ),
                    Expanded(
                      child: messages.isEmpty
                          ? const Center(
                              child: Text(
                                'Inicia la conversación sobre este material.',
                              ),
                            )
                          : ListView.builder(
                              controller: scroll,
                              padding: const EdgeInsets.all(16),
                              itemCount: messages.length,
                              itemBuilder: (context, index) {
                                final message = messages[index];
                                final mine = message['sender_id'] == userId;
                                return Align(
                                  alignment: mine
                                      ? Alignment.centerRight
                                      : Alignment.centerLeft,
                                  child: Container(
                                    constraints: BoxConstraints(
                                      maxWidth:
                                          MediaQuery.sizeOf(context).width * .8,
                                    ),
                                    margin: const EdgeInsets.only(bottom: 12),
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: mine
                                          ? const Color(0xffd5e8ce)
                                          : Colors.white,
                                      borderRadius: BorderRadius.circular(14),
                                    ),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          message['content'] as String,
                                          key: Key('message-${message['id']}'),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          dateTimeLabel(message['created_at']),
                                          style: const TextStyle(fontSize: 10),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                    ),
                    if (!compact &&
                        data != null &&
                        (data!['meeting_points'] as List? ?? []).isNotEmpty)
                      SizedBox(
                        height: 38,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          children: [
                            for (final point in data!['meeting_points'] as List)
                              Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: ActionChip(
                                  label: Text(point.toString()),
                                  onPressed: sending
                                      ? null
                                      : () =>
                                            text.text = '¿Nos vemos en $point?',
                                ),
                              ),
                          ],
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Expanded(
                            child: TextField(
                              key: const Key('chat-input'),
                              controller: text,
                              enabled: !sending,
                              minLines: 1,
                              maxLines: compact ? 1 : 3,
                              maxLength: 1000,
                              decoration: const InputDecoration(
                                hintText: 'Escribe un mensaje',
                                counterText: '',
                              ),
                              onSubmitted: (_) => _send(),
                            ),
                          ),
                          IconButton(
                            key: const Key('send-message'),
                            tooltip: 'Enviar mensaje',
                            onPressed: sending || data == null ? null : _send,
                            icon: Icon(
                              sending ? Icons.hourglass_top : Icons.send,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

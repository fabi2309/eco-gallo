import 'package:material_ui/material_ui.dart';

import 'dart:async';

import 'core/api_client.dart';

import 'core/session_controller.dart';
import 'core/photo_picker_service.dart';
import 'features/auth/auth_screen.dart';
import 'features/catalog/catalog_screen.dart';
import 'ui/shared.dart';

class EcoGalloApp extends StatefulWidget {
  const EcoGalloApp({super.key, this.api, this.photoPicker, this.saveServer});
  final ApiClient? api;
  final PhotoPickerService? photoPicker;
  final Future<void> Function(String)? saveServer;
  @override
  State<EcoGalloApp> createState() => _EcoGalloAppState();
}

class _EcoGalloAppState extends State<EcoGalloApp> with WidgetsBindingObserver {
  late final session = SessionController(
    widget.api ?? ApiClient(),
    saveServer: widget.saveServer,
  );
  late final photos = widget.photoPicker ?? PhotoPickerService();
  final navigator = GlobalKey<NavigatorState>();
  Timer? _inboxTimer;
  bool _foreground = true, _checkingInbox = false, _inboxAgain = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _foreground =
        WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    session.api.onInboxChanged = _refreshInbox;
    _startInboxTimer();
    photos.startRecovery();
    session.addListener(_changed);
    session.initialize();
  }

  void _startInboxTimer() {
    _inboxTimer?.cancel();
    if (_foreground) {
      _inboxTimer = Timer.periodic(
        const Duration(seconds: 30),
        (_) => _refreshInbox(),
      );
    }
  }

  Future<void> _refreshInbox() async {
    if (!mounted ||
        !_foreground ||
        session.busy ||
        ![
          SessionPhase.signedIn,
          SessionPhase.pending,
        ].contains(session.phase)) {
      return;
    }
    if (_checkingInbox) {
      _inboxAgain = true;
      return;
    }
    _checkingInbox = true;
    try {
      await session.refreshSession();
    } on ApiException {
      /* Preserve the current view during a temporary network failure. */
    } finally {
      _checkingInbox = false;
      if (_inboxAgain) {
        _inboxAgain = false;
        if (mounted && _foreground) _refreshInbox();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    _startInboxTimer();
    if (_foreground) _refreshInbox();
  }

  void _changed() {
    if (session.phase != SessionPhase.signedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && session.phase != SessionPhase.signedIn) {
          navigator.currentState?.popUntil((route) => route.isFirst);
        }
      });
    }
  }

  @override
  void dispose() {
    _inboxTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    session.api.onInboxChanged = null;
    session.removeListener(_changed);
    session.dispose();
    session.api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'ECO-GALLO',
    debugShowCheckedModeBanner: false,
    navigatorKey: navigator,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: paper,
      colorScheme: ColorScheme.fromSeed(seedColor: forest),
      appBarTheme: const AppBarTheme(backgroundColor: paper),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        ),
      ),
    ),
    home: AnimatedBuilder(
      animation: session,
      builder: (context, _) => switch (session.phase) {
        SessionPhase.loading => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
        SessionPhase.signedOut => AuthScreen(session),
        SessionPhase.profile => ProfileCompletionScreen(session),
        SessionPhase.signedIn => CatalogScreen(session, photos),
        SessionPhase.offline => Scaffold(
          appBar: AppBar(
            title: const Brand(),
            actions: [ServerButton(session)],
          ),
          body: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off_outlined, size: 64, color: forest),
                  const SizedBox(height: 16),
                  const Text(
                    'Conecta con tu comunidad',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  ErrorNotice(session.error),
                  FilledButton(
                    onPressed: session.initialize,
                    child: const Text('Reintentar'),
                  ),
                  TextButton(
                    onPressed: () => connectionDialog(context, session),
                    child: const Text('Configurar conexión'),
                  ),
                ],
              ),
            ),
          ),
        ),
        SessionPhase.pending => Scaffold(
          appBar: AppBar(title: const Brand()),
          body: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.hourglass_top, size: 60, color: forest),
                  const Text(
                    'Tu cuenta requiere verificación',
                    style: TextStyle(fontSize: 24),
                  ),
                  Text(
                    session.verificationMessage.isEmpty
                        ? 'Completa la verificación de egresado desde la web.'
                        : session.verificationMessage,
                  ),
                  ErrorNotice(session.error),
                  FilledButton(
                    onPressed: session.busy ? null : session.initialize,
                    child: const Text('Revisar estado'),
                  ),
                  TextButton(
                    onPressed: session.busy ? null : session.logout,
                    child: const Text('Cerrar sesión'),
                  ),
                ],
              ),
            ),
          ),
        ),
      },
    ),
  );
}

import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../../core/session_controller.dart';
import '../../ui/shared.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen(this.session, {super.key});
  final SessionController session;
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();
  final _form = GlobalKey<FormState>();
  bool _useCode = false, _sent = false, _obscure = true;
  String? _devCode;
  int _cooldown = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _email.dispose();
    _password.dispose();
    _code.dispose();
    super.dispose();
  }

  void _setCooldown(int seconds) {
    _timer?.cancel();
    _cooldown = seconds;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      setState(() {
        if (_cooldown > 0) _cooldown--;
        if (_cooldown == 0) timer.cancel();
      });
    });
  }

  Future<void> _send() async {
    final result = await widget.session.action(
      () => widget.session.api.post('/api/auth/request-code', {
        'email': _email.text.trim().toLowerCase(),
      }),
    );
    if (!mounted || result == null) return;
    setState(() {
      _sent = true;
      _devCode = result['dev_code'] as String?;
      _code.clear();
      _setCooldown(result['cooldown'] as int? ?? 45);
    });
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final session = widget.session;
    if (session.challenge != null) {
      await session.verifyTotp(_code.text);
    } else if (!_useCode) {
      await session.login(_email.text, _password.text);
    } else if (!_sent) {
      await _send();
    } else {
      await session.verifyCode(_email.text, _code.text);
    }
    if (mounted &&
        (session.phase != SessionPhase.signedOut ||
            session.challenge != null)) {
      _password.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final totp = session.challenge != null;
    final title = totp
        ? 'Una última verificación'
        : _sent
        ? 'Revisa tu correo'
        : 'Hola, gallo.';
    return Scaffold(
      appBar: AppBar(title: const Brand(), actions: [ServerButton(session)]),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 22),
                  Container(
                    padding: const EdgeInsets.all(15),
                    decoration: BoxDecoration(
                      color: lime,
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: const Icon(
                      Icons.recycling_rounded,
                      size: 44,
                      color: forest,
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text(
                    title,
                    style: Theme.of(context).textTheme.headlineLarge
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    totp
                        ? 'Escribe el código de tu autenticador o un código de recuperación.'
                        : _sent
                        ? 'Ingresa el código que enviamos a ${_email.text.trim()}.'
                        : 'Lo que ya no usas puede empezar una nueva historia. Encuentra materiales de tu comunidad UAA.',
                    style: Theme.of(context).textTheme.bodyLarge
                        ?.copyWith(color: const Color(0xff55675b)),
                  ),
                  const SizedBox(height: 28),
                  Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (!totp && !_sent) ...[
                          TextFormField(
                            key: const Key('email'),
                            controller: _email,
                            enabled: !session.busy,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.email],
                            autocorrect: false,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Correo',
                              prefixIcon: Icon(Icons.alternate_email),
                            ),
                            validator: (v) => v == null || !v.contains('@')
                                ? 'Escribe tu correo completo.'
                                : null,
                          ),
                          const SizedBox(height: 16),
                          if (!_useCode)
                            TextFormField(
                              key: const Key('password'),
                              controller: _password,
                              enabled: !session.busy,
                              obscureText: _obscure,
                              autofillHints: const [AutofillHints.password],
                              textInputAction: TextInputAction.done,
                              onFieldSubmitted: (_) => _submit(),
                              decoration: InputDecoration(
                                labelText: 'Contraseña',
                                prefixIcon: const Icon(Icons.lock_outline),
                                suffixIcon: IconButton(
                                  tooltip: _obscure
                                      ? 'Mostrar contraseña'
                                      : 'Ocultar contraseña',
                                  onPressed: () =>
                                      setState(() => _obscure = !_obscure),
                                  icon: Icon(
                                    _obscure
                                        ? Icons.visibility_outlined
                                        : Icons.visibility_off_outlined,
                                  ),
                                ),
                              ),
                              validator: (v) => v == null || v.isEmpty
                                  ? 'Escribe tu contraseña.'
                                  : null,
                            ),
                        ],
                        if (_sent || totp)
                          TextFormField(
                            key: const Key('code'),
                            controller: _code,
                            enabled: !session.busy,
                            keyboardType: totp
                                ? TextInputType.text
                                : TextInputType.number,
                            maxLength: totp ? 12 : 6,
                            autofillHints: const [AutofillHints.oneTimeCode],
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submit(),
                            decoration: InputDecoration(
                              labelText: totp
                                  ? 'Código de autenticación'
                                  : 'Código de 6 dígitos',
                              prefixIcon: const Icon(
                                Icons.verified_user_outlined,
                              ),
                            ),
                            validator: (value) {
                              if (totp) {
                                return RegExp(r'^(\d{6}|[a-fA-F0-9]{12})$')
                                        .hasMatch(value?.trim() ?? '')
                                    ? null
                                    : 'Escribe un código válido.';
                              }
                              return RegExp(r'^\d{6}$')
                                      .hasMatch(value?.trim() ?? '')
                                  ? null
                                  : 'Escribe los 6 dígitos.';
                            },
                          ),
                        if (_devCode != null && !totp)
                          Container(
                            margin: const EdgeInsets.only(top: 12),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: const Color(0xfff7f2cf),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(
                              'Solo desarrollo · Código: $_devCode',
                              key: const Key('dev-code'),
                            ),
                          ),
                        ErrorNotice(session.error),
                        const SizedBox(height: 8),
                        FilledButton(
                          key: const Key('sign-in'),
                          onPressed: session.busy ? null : _submit,
                          child: session.busy
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : Text(
                                  totp || _sent
                                      ? 'Verificar código'
                                      : _useCode
                                      ? 'Enviar código'
                                      : 'Entrar',
                                ),
                        ),
                        const SizedBox(height: 12),
                        if (!_sent && !totp)
                          TextButton(
                            key: const Key('toggle-code'),
                            onPressed: session.busy
                                ? null
                                : () {
                                    setState(() {
                                      _useCode = !_useCode;
                                      session.error = null;
                                      _password.clear();
                                    });
                                  },
                            child: Text(
                              _useCode
                                  ? 'Entrar con contraseña'
                                  : 'Primera vez o sin contraseña: usar código',
                            ),
                          ),
                        if (_sent && !totp)
                          TextButton(
                            onPressed: session.busy || _cooldown > 0
                                ? null
                                : _send,
                            child: Text(
                              _cooldown > 0
                                  ? 'Reenviar en $_cooldown s'
                                  : 'Reenviar código',
                            ),
                          ),
                        if (_sent || totp)
                          TextButton(
                            onPressed: session.busy
                                ? null
                                : () {
                                    session.resetChallenge();
                                    setState(() {
                                      _sent = false;
                                      _devCode = null;
                                      _code.clear();
                                    });
                                  },
                            child: const Text('Volver al acceso'),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  PaymentNotice(session.paymentMode),
                  const SizedBox(height: 14),
                  const Text(
                    'Materiales que circulan. Comunidad que crece.',
                    style: TextStyle(color: forest, fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ProfileCompletionScreen extends StatefulWidget {
  const ProfileCompletionScreen(this.session, {super.key});
  final SessionController session;
  @override
  State<ProfileCompletionScreen> createState() =>
      _ProfileCompletionScreenState();
}

class _ProfileCompletionScreenState extends State<ProfileCompletionScreen> {
  final _name = TextEditingController();
  final _form = GlobalKey<FormState>();
  String? _career;
  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Tu comunidad UAA'),
      actions: [
        IconButton(
          onPressed: widget.session.busy ? null : widget.session.logout,
          tooltip: 'Cerrar sesión',
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            'Antes de comenzar',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          const Text(
            'Completa tu nombre y carrera. Tu centro académico se asignará automáticamente.',
          ),
          const SizedBox(height: 24),
          Form(
            key: _form,
            child: Column(
              children: [
                TextFormField(
                  key: const Key('profile-name'),
                  controller: _name,
                  maxLength: 80,
                  decoration: const InputDecoration(
                    labelText: 'Nombre completo',
                  ),
                  validator: (v) => (v?.trim().length ?? 0) < 3
                      ? 'Escribe al menos 3 caracteres.'
                      : null,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  key: const Key('profile-career'),
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Carrera'),
                  items: widget.session.carreras
                      .map(
                        (c) => DropdownMenuItem(
                          value: c,
                          child: Text(c, overflow: TextOverflow.ellipsis),
                        ),
                      )
                      .toList(),
                  onChanged: (c) => _career = c,
                  validator: (v) => v == null ? 'Elige tu carrera.' : null,
                ),
                ErrorNotice(widget.session.error),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: widget.session.busy
                      ? null
                      : () {
                          if (_form.currentState!.validate()) {
                            widget.session.completeProfile(
                              _name.text,
                              _career!,
                            );
                          }
                        },
                  child: const Text('Guardar y continuar'),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

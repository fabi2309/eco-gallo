"""Servidor de tesina con los datos principales; LAN o solamente USB."""
import argparse
from contextlib import closing
from datetime import datetime
import os
from pathlib import Path
import socket
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent


def configure(data: Path, local_codes=False):
    data = data.resolve()
    database = data / 'ecogallo.sqlite'
    if not database.is_file() or not (data / 'secret.key').is_file():
        raise ValueError(f'No se encontró la base existente y su secret.key en {data}. No se crearon datos nuevos.')
    # Back up SQLite consistently, including WAL, before normal startup/migrations.
    backups = data / 'backups'
    backups.mkdir(exist_ok=True)
    backup = backups / f'antes-movil-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite'
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
    os.environ.update({
        'ECOGALLO_DATA': str(data), 'ECOGALLO_ENV': 'development',
        'ECOGALLO_DEV': '1' if local_codes else '0', 'ECOGALLO_SEED': '0', 'ECOGALLO_ADMINS': '',
        'ECOGALLO_ADMIN_PASSWORD': '', 'ECOGALLO_NO_DOTENV': '1',
        'ECOGALLO_PUBLIC_URL': '', 'ECOGALLO_SECURE': '0',
        'PAYMENT_PROVIDER': 'simulado', 'ECOGALLO_LIVE_PAYMENTS': '0',
        'ECOGALLO_CONNECT_SIMULATED': '0', 'ECOGALLO_RECONCILE_ENABLED': '0',
        'STRIPE_SECRET_KEY': '', 'STRIPE_PUBLISHABLE_KEY': '', 'STRIPE_WEBHOOK_SECRET': '',
        'MERCADOPAGO_ACCESS_TOKEN': '', 'MERCADOPAGO_WEBHOOK_SECRET': '',
        **({'TWILIO_ACCOUNT_SID': '', 'TWILIO_AUTH_TOKEN': '', 'TWILIO_FROM': '',
            'ECOGALLO_SMTP_HOST': ''} if local_codes else {}),
    })
    # SMTP environment settings are preserved. Without SMTP, use an existing
    # password: access codes are never returned to clients on the LAN.
    return backup


def local_addresses():
    try:
        return sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                       if not item[4][0].startswith('127.')})
    except OSError:
        return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usb', action='store_true', help='Escuchar solo en la propia PC para el túnel USB')
    parser.add_argument('--codigos-locales', action='store_true', help='Códigos ficticios de correo/SMS, solo con --usb')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--data', type=Path, default=ROOT / 'data', help='Carpeta existente de datos del proyecto')
    args = parser.parse_args()
    if args.codigos_locales and not args.usb:
        parser.error('--codigos-locales requiere --usb; no se muestran códigos en la red local.')
    if not 1 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 1 y 65535.')
    host = '127.0.0.1' if args.usb else '0.0.0.0'
    # Reserve the port before importing the app or touching the principal DB.
    with socket.socket() as probe:
        try:
            probe.bind((host, args.port))
        except OSError:
            raise SystemExit(f'El puerto {args.port} está ocupado. Detén el servidor anterior desde su terminal.')
    try:
        backup = configure(args.data, local_codes=args.codigos_locales)
    except ValueError as error:
        raise SystemExit(str(error))
    sys.path.insert(0, str(ROOT))
    from webapp import app
    from flask import send_file
    from waitress import serve

    @app.get('/descargas/ecogallo-local.apk')
    def download_apk():
        apk = ROOT / 'artifacts' / 'mobile' / 'ECO-GALLO-local.apk'
        if not apk.is_file():
            return {'ok': False, 'message': 'Genera primero el APK con crear_apk_local.bat.'}, 404
        return send_file(apk, as_attachment=True, download_name='ECO-GALLO-local.apk',
                         mimetype='application/vnd.android.package-archive', max_age=0)

    print(f'Datos principales: {args.data.resolve()}\nRespaldo previo: {backup}', flush=True)
    print('Cuentas existentes. Sin siembra de demo. Pagos exclusivamente simulados.', flush=True)
    print(f'PC y USB: http://127.0.0.1:{args.port}', flush=True)
    if not args.usb:
        for ip in local_addresses():
            print(f'Posible dirección Wi-Fi: http://{ip}:{args.port}', flush=True)
        print('HTTP local: usa una red de confianza. No abras el puerto al Internet. '
              'Para redes aisladas usa conectar_movil_usb.bat.', flush=True)
    serve(app, host=host, port=args.port, threads=4, max_request_body_size=25 * 1024 * 1024)


if __name__ == '__main__':
    main()

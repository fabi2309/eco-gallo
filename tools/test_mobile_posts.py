r"""Prueba Android con servidor, cuentas e imágenes aisladas de los datos del usuario.

Uso: .venv\Scripts\python.exe tools\test_mobile_posts.py [emulator-5554] [posts|community|stability|extended]
Requiere Flutter y Android SDK instalados; no detiene el servidor demo de 8080.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    device = sys.argv[1] if len(sys.argv) > 1 else 'emulator-5554'
    if not re.fullmatch(r'[A-Za-z0-9_.:-]+', device):
        raise SystemExit('Serial de dispositivo no válido.')
    suite = sys.argv[2] if len(sys.argv) > 2 else 'posts'
    if suite not in ('posts', 'community', 'stability', 'extended'):
        raise SystemExit('Suite no válida: posts, community, stability o extended.')
    flutter = shutil.which('flutter') or shutil.which('flutter.bat')
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
               or Path(os.environ['LOCALAPPDATA']) / 'Android' / 'Sdk')
    adb = sdk / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
    if not flutter or not adb.is_file():
        raise SystemExit('Flutter o adb no están disponibles.')
    with tempfile.TemporaryDirectory(prefix='ecogallo-mobile-posts-') as data_dir:
        os.environ.update({
            'ECOGALLO_DATA': data_dir, 'ECOGALLO_ENV': 'development', 'ECOGALLO_DEV': '1',
            'ECOGALLO_SEED': '1', 'PAYMENT_PROVIDER': 'simulado', 'ECOGALLO_LIVE_PAYMENTS': '0',
            'ECOGALLO_BACKUP_ENABLED': '0', 'ECOGALLO_RECONCILE_ENABLED': '0',
            'ECOGALLO_SMTP_HOST': '', 'ECOGALLO_PUBLIC_URL': '', 'ECOGALLO_ADMINS': '',
            'STRIPE_SECRET_KEY': '', 'STRIPE_PUBLISHABLE_KEY': '', 'STRIPE_WEBHOOK_SECRET': '',
            'ECOGALLO_NO_DOTENV': '1', 'MERCADOPAGO_ACCESS_TOKEN': '', 'MERCADOPAGO_WEBHOOK_SECRET': '',
            'TWILIO_ACCOUNT_SID': '', 'TWILIO_AUTH_TOKEN': '', 'TWILIO_FROM': '',
        })
        from webapp import app
        from db import connect, now
        from security import hash_password
        import catalog
        from werkzeug.serving import make_server

        carrera = next(iter(catalog.CENTROS_CARRERAS.values()))[0]
        con = connect()
        try:
            for email, role in [('editor@edu.uaa.mx', 'user'), ('revisor@edu.uaa.mx', 'admin'), ('otro@edu.uaa.mx', 'user'), ('curioso@edu.uaa.mx', 'user')]:
                con.execute('''INSERT INTO users(email,name,carrera,centro,created_at,password_hash,role)
                               VALUES(?,?,?,?,?,?,?)''',
                            (email, 'Prueba Móvil', carrera, catalog.centro_de(carrera), now(), hash_password('PruebaMovil123'), role))
            if suite in ('community', 'extended'):
                seller_id = con.execute('SELECT id FROM users WHERE email=?', ('editor@edu.uaa.mx',)).fetchone()[0]
                for title in ('Libro venta móvil', 'Libro disputa móvil', 'Libro reembolso móvil'):
                    con.execute('''INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,status,created_at)
                                   VALUES(?,?,?,?,?,'venta',10000,'Usado','active',?)''',
                                (seller_id, title, 'Libro de prueba para reutilizar en la comunidad.', 'Libros', 'General', now()))
                con.execute('''INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,status,created_at)
                               VALUES(?,?,?,?,?,'donacion',0,'Usado','active',?)''',
                            (seller_id, 'Donación móvil de prueba', 'Material para compartir con la comunidad.', 'Libros', 'General', now()))
            import config
            for user in con.execute("SELECT id FROM users WHERE email IN ('editor@edu.uaa.mx','revisor@edu.uaa.mx','otro@edu.uaa.mx','curioso@edu.uaa.mx')").fetchall():
                con.execute("UPDATE users SET terms_version=?,terms_accepted_at=?,phone=?,phone_verified_at=?,payout_kind='tarjeta',payout_last4='4242',payout_holder='Prueba Movil' WHERE id=?",
                            (config.LEGAL_VERSION, now(), f'+52449{user[0]:07d}', now(), user[0]))
            if suite == 'extended':
                con.execute("UPDATE users SET terms_version='',phone='',phone_verified_at=0,payout_kind='',payout_last4='' WHERE email='curioso@edu.uaa.mx'")
        finally:
            con.close()
        server = make_server('127.0.0.1', 8081, app, threaded=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            subprocess.run([str(adb), '-s', device, 'reverse', 'tcp:8081', 'tcp:8081'], check=True)
            test_file = {'posts': 'posts_flow_test.dart', 'community': 'community_flow_test.dart',
                         'stability': 'mobile_stability_test.dart', 'extended': 'extended_flow_test.dart'}[suite]
            command = [flutter, 'test', f'integration_test/{test_file}', '-d', device,
                       '--dart-define=API_BASE_URL=http://127.0.0.1:8081']
            if os.environ.get('ECOGALLO_NATIVE_PICKER_CHECK') == '1':
                command.append('--dart-define=NATIVE_PICKER_CHECK=true')
            if os.name == 'nt':
                command = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', *command]
            result = subprocess.run(command, cwd=ROOT / 'mobile', check=False)
            return result.returncode
        finally:
            subprocess.run([str(adb), '-s', device, 'reverse', '--remove', 'tcp:8081'], check=False)
            server.shutdown()
            server.server_close()
            worker.join(timeout=10)


if __name__ == '__main__':
    raise SystemExit(main())

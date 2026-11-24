"""Demo local aislada para Flutter. Nunca usa la base de datos habitual."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for key, value in {
    'ECOGALLO_DATA': str(ROOT / 'data' / 'mobile-demo'),
    'ECOGALLO_ENV': 'development', 'ECOGALLO_DEV': '1', 'ECOGALLO_SEED': '1',
    'ECOGALLO_LIVE_PAYMENTS': '0', 'PAYMENT_PROVIDER': 'simulado',
    'ECOGALLO_BACKUP_ENABLED': '0', 'ECOGALLO_RECONCILE_ENABLED': '0',
    'ECOGALLO_SMTP_HOST': '', 'STRIPE_SECRET_KEY': '',
    'STRIPE_PUBLISHABLE_KEY': '', 'STRIPE_WEBHOOK_SECRET': '',
    'ECOGALLO_PUBLIC_URL': '', 'ECOGALLO_ADMINS': '',
    'ECOGALLO_NO_DOTENV': '1', 'MERCADOPAGO_ACCESS_TOKEN': '', 'MERCADOPAGO_WEBHOOK_SECRET': '',
    'TWILIO_ACCOUNT_SID': '', 'TWILIO_AUTH_TOKEN': '', 'TWILIO_FROM': '',
}.items():
    os.environ[key] = value

from webapp import app  # noqa: E402
from db import connect, now  # noqa: E402
from security import hash_password  # noqa: E402
import catalog  # noqa: E402


def main():
    carrera = next(iter(catalog.CENTROS_CARRERAS.values()))[0]
    con = connect()
    try:
        accounts = [
            ('movil@edu.uaa.mx', 'Estudiante Demo', 'EcoGalloDemo123', 'user'),
            ('revision@edu.uaa.mx', 'Revisión Demo', 'EcoGalloRevision123', 'admin'),
            ('companero-demo@edu.uaa.mx', 'Compañero Demo', 'EcoGalloDemo123', 'user'),
        ]
        for email, name, password, role in accounts:
            if not con.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                created = con.execute('''INSERT INTO users(email,name,carrera,centro,created_at,password_hash,role)
                               VALUES(?,?,?,?,?,?,?)''',
                                      (email, name, carrera, catalog.centro_de(carrera), now(), hash_password(password), role))
                if email == 'companero-demo@edu.uaa.mx':
                    con.execute('''INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,status,created_at)
                                   VALUES(?,?,?,?,?,'venta',5000,'Usado','active',?)''',
                                (created.lastrowid, 'Libro para probar pedidos',
                                 'Publicación ficticia para probar mensajes, entrega y pago simulado entre las cuentas de demostración.',
                                 'Libros', catalog.centro_de(carrera), now()))
    finally:
        con.close()
    print('Demo aislada: http://127.0.0.1:8080\n'
          'Correo: movil@edu.uaa.mx | Contraseña: EcoGalloDemo123\n'
          'Revisión desde la web: revision@edu.uaa.mx | Contraseña: EcoGalloRevision123\n'
          'Segunda cuenta: companero-demo@edu.uaa.mx | Contraseña: EcoGalloDemo123\n'
          'Solo pruebas locales. Datos: data/mobile-demo. Ctrl+C para detener.', flush=True)
    app.run(host='127.0.0.1', port=8080, debug=False, threaded=True)


if __name__ == '__main__':
    main()

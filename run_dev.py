"""Local development only. Production uses run_prod.py."""
import os

if os.environ.get('ECOGALLO_ENV') == 'production':
    raise RuntimeError('Usa run_prod.py para producción.')
from backend_path import setup_backend  # noqa: E402

setup_backend()
import envfile  # noqa: E402

envfile.load()  # primero el archivo .env (si existe); después los valores por defecto de la demostración
os.environ.setdefault('ECOGALLO_DEV', '1')
os.environ.setdefault('ECOGALLO_SEED', '1')
os.environ.setdefault('ECOGALLO_ADMINS', 'admin@edu.uaa.mx')

from webapp import app  # noqa: E402

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    print(f'ECO-GALLO local: http://127.0.0.1:{port}')
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)

"""Local development only. Production uses run_prod.py."""
import os

if os.environ.get('ECOGALLO_ENV') == 'production':
    raise RuntimeError('Usa run_prod.py para producción.')
os.environ.setdefault('ECOGALLO_DEV', '1')

from webapp import app  # noqa: E402

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    print(f'ECO-GALLO local: http://127.0.0.1:{port}')
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)

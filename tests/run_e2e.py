"""Run the API suite over real HTTP against Waitress and a disposable database."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix='ecogallo-e2e-') as data:
        os.environ.update(ECOGALLO_DATA=data, ECOGALLO_DEV='1', ECOGALLO_ENV='development',
                          ECOGALLO_BACKUP_ENABLED='0', ECOGALLO_RECONCILE_ENABLED='0',
                          PAYMENT_PROVIDER='simulado', ECOGALLO_AUTH_LIMIT='1000',
                          ECOGALLO_ADMINS='admin@edu.uaa.mx')
        from webapp import app
        from waitress import create_server
        server = create_server(app, host='127.0.0.1', port=0, threads=8)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tests' / 'e2e_api.py'),
                                     f'http://127.0.0.1:{server.effective_port}'], cwd=ROOT, timeout=240)
            return result.returncode
        finally:
            server.close()
            # Drop idle per-request SQLite handles before deleting the disposable directory.
            server.task_dispatcher.shutdown(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())

"""Fresh-process smoke test: production startup and host checks use real configuration."""
import os
from pathlib import Path
import subprocess
import sys


def test_production_app_can_boot_without_enabling_payments(tmp_path):
    env = dict(os.environ)
    env.update(ECOGALLO_ENV='production', ECOGALLO_DEV='0', ECOGALLO_SEED='0',
               ECOGALLO_SECURE='1', ECOGALLO_PUBLIC_URL='https://market.example',
               ECOGALLO_SECRET='test-only-persistent-secret-at-least-32-chars', ECOGALLO_SMTP_HOST='smtp.example',
               ECOGALLO_PRIVACY_EMAIL='privacidad@market.example', ECOGALLO_NO_DOTENV='1',
               ECOGALLO_DATA=str(tmp_path), ECOGALLO_BACKUP_ENABLED='0', ECOGALLO_RECONCILE_ENABLED='0',
               PAYMENT_PROVIDER='disabled', STRIPE_SECRET_KEY='', ECOGALLO_CONNECT_SIMULATED='0')
    script = '''from webapp import app
c=app.test_client()
r=c.get('/api/health',headers={'Host':'market.example'})
assert r.status_code==200, r.data
assert r.headers['Strict-Transport-Security']
assert c.get('/api/health',headers={'Host':'evil.example'}).status_code==400
assert c.get('/api/meta',headers={'Host':'market.example'}).json['payment_mode']=='disabled'
assert c.get('/',headers={'Host':'market.example'}).status_code==200
assert not app.debug
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script], env=env,
                            cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr

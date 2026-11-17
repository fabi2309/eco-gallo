"""Never run tests against workspace data or enable background services."""
import os
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

os.environ['ECOGALLO_DATA'] = tempfile.mkdtemp(prefix='ecogallo-pytest-')
os.environ['ECOGALLO_BACKUP_ENABLED'] = '0'
os.environ['ECOGALLO_RECONCILE_ENABLED'] = '0'
os.environ['ECOGALLO_DEV'] = '1'
os.environ['ECOGALLO_ENV'] = 'development'
os.environ['PAYMENT_PROVIDER'] = 'simulado'
os.environ['ECOGALLO_AUTH_LIMIT'] = '1000'

"""The local launcher must neither seed nor replace principal records."""
import os
import sqlite3

import pytest

from tools.run_mobile_local import configure


def test_launcher_preserves_database_and_backs_up(tmp_path, monkeypatch):
    # Restore every environment key after this test; configure changes only env.
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    (tmp_path / 'secret.key').write_text('existing-secret')
    database = tmp_path / 'ecogallo.sqlite'
    with sqlite3.connect(database) as con:
        con.execute('CREATE TABLE sentinel(value TEXT)')
        con.execute("INSERT INTO sentinel VALUES('principal')")
    monkeypatch.setenv('ECOGALLO_DATA', 'data/mobile-demo')
    monkeypatch.setenv('ECOGALLO_DEV', '1')
    monkeypatch.setenv('ECOGALLO_SEED', '1')
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_live_dont_use')
    backup = configure(tmp_path)
    for path in (database, backup):
        with sqlite3.connect(path) as con:
            assert con.execute('SELECT * FROM sentinel').fetchall() == [('principal',)]
    assert (tmp_path / 'secret.key').read_text() == 'existing-secret'
    assert os.environ['ECOGALLO_DATA'] == str(tmp_path.resolve())
    assert os.environ['ECOGALLO_DEV'] == os.environ['ECOGALLO_SEED'] == '0'
    assert os.environ['STRIPE_SECRET_KEY'] == ''
    assert os.environ['PAYMENT_PROVIDER'] == 'simulado'


def test_launcher_refuses_to_create_a_different_database(tmp_path):
    with pytest.raises(ValueError, match='No se crearon datos nuevos'):
        configure(tmp_path)
    assert not (tmp_path / 'ecogallo.sqlite').exists()

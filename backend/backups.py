"""Módulo de respaldos automáticos y bajo demanda de ECO-GALLO UAA.

Empaqueta de forma atómica y consistente:
- La base de datos SQLite (usando la API online de sqlite3.Connection.backup).
- El directorio de imágenes y fotografías subidas (data/uploads/).
- Los documentos de verificación pendientes (data/private/verificaciones/).
- Metadatos del respaldo (meta.json).
Aplica política de rotación reteniendo los N respaldos más recientes.
"""
import datetime
import json
import logging
import pathlib
import sqlite3
import tempfile
import threading
import time
import zipfile

import config

log = logging.getLogger("ecogallo.backups")

_scheduler_started = False
_scheduler_lock = threading.Lock()


def human_size(n: int) -> str:
    """Convierte bytes a formato legible (KB, MB, GB)."""
    val = float(n)
    for unit in ["B", "KB", "MB", "GB"]:
        if val < 1024 or unit == "GB":
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024
    return f"{val:.1f} TB"


def rotate_backups():
    """Conserva únicamente los N respaldos más recientes según config.BACKUP_KEEP."""
    config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backups = sorted(
        config.BACKUPS_DIR.glob("ecogallo_backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[config.BACKUP_KEEP:]:
        try:
            old.unlink(missing_ok=True)
            log.info("Respaldo antiguo rotado/eliminado: %s", old.name)
        except OSError as e:
            log.warning("No se pudo eliminar respaldo antiguo %s: %s", old.name, e)


MAX_ARCHIVE = 200 * 1024 * 1024
MAX_UNPACKED = 128 * 1024 * 1024


def _cipher():
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'ecogallo-backup-v1:' + config.SECRET).digest()))


def _safe_entries(zf):
    total = 0
    seen = set()
    for item in zf.infolist():
        path = pathlib.PurePosixPath(item.filename)
        if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename
                or item.filename in seen or len(path.parts) > 10):
            raise ValueError('El respaldo contiene rutas no seguras o repetidas.')
        seen.add(item.filename)
        total += item.file_size
        if total > MAX_UNPACKED or item.file_size > MAX_UNPACKED:
            raise ValueError('El respaldo supera el límite de tamaño descomprimido.')
        if len(seen) > 20000:
            raise ValueError('El respaldo contiene demasiados archivos.')
    return total


def _read_backup(path):
    import io
    from cryptography.fernet import InvalidToken
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('El respaldo supera el límite permitido.')
    try:
        with zipfile.ZipFile(path) as outer:
            names = set(outer.namelist())
            if names != {'meta.json', 'payload.enc'} or len(outer.namelist()) != 2:
                raise ValueError('Se requiere un respaldo cifrado v2. Conserva los respaldos antiguos y migra desde su entorno original.')
            if any(i.file_size > MAX_ARCHIVE for i in outer.infolist()):
                raise ValueError('El respaldo supera el límite permitido.')
            if outer.getinfo('meta.json').file_size > 65536:
                raise ValueError('Metadatos demasiado grandes.')
            meta = json.loads(outer.read('meta.json'))
            raw = _cipher().decrypt(outer.read('payload.enc'))
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            _safe_entries(inner)
            if 'metadata.json' not in inner.namelist() or inner.getinfo('metadata.json').file_size > 65536:
                raise ValueError('Faltan metadatos autenticados.')
            if json.loads(inner.read('metadata.json')) != meta:
                raise ValueError('Los metadatos del respaldo fueron alterados.')
            if 'database/ecogallo.sqlite' not in inner.namelist():
                raise ValueError('Falta la base de datos del respaldo.')
            for item in inner.infolist():
                if item.filename not in ('database/ecogallo.sqlite', 'metadata.json') and not item.filename.startswith(('uploads/', 'verificaciones/')):
                    raise ValueError('El respaldo contiene archivos inesperados.')
        return meta, raw
    except InvalidToken:
        raise ValueError('La clave del sistema no corresponde al respaldo o el archivo fue alterado. Recupera ECOGALLO_SECRET original.') from None
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        raise ValueError('El archivo no es un respaldo válido.') from None


def _create_backup(tag='manual'):
    import io
    import uuid
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    stamp = now_dt.strftime('%Y%m%d_%H%M%S')
    clean_tag = ''.join(c for c in str(tag)[:40] if c.isalnum() or c in ('-', '_')) or 'manual'
    filename = f'ecogallo_backup_{stamp}_{clean_tag}_{uuid.uuid4().hex[:8]}.zip'
    dest = config.BACKUPS_DIR / filename
    config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stats = {}
    uploads_count = 0
    with tempfile.TemporaryDirectory() as tmp:
        temp_db = pathlib.Path(tmp) / 'ecogallo.sqlite'
        src = sqlite3.connect(config.DB_PATH)
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
            stats = {t: dst.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('users', 'posts', 'orders')}  # nosec B608 - SQL structure from fixed constants; user values are bound parameters
        finally:
            src.close()
            dst.close()
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(temp_db, 'database/ecogallo.sqlite')
            for directory, prefix in ((config.UPLOADS, 'uploads'), (config.VERIF_DIR, 'verificaciones')):
                for item in directory.rglob('*'):
                    if item.is_symlink():
                        raise ValueError('No se admiten enlaces simbólicos en los datos.')
                    if item.is_file():
                        zf.write(item, f'{prefix}/{item.relative_to(directory).as_posix()}')
                        uploads_count += prefix == 'uploads'
            _safe_entries(zf)
        if raw.tell() > MAX_UNPACKED:
            raise ValueError('El conjunto de datos supera el límite del respaldo integrado; usa el procedimiento externo.')
        meta = {'version': 2, 'system': 'ECO-GALLO UAA', 'created_at': now_dt.isoformat(),
                'created_timestamp': int(now_dt.timestamp()), 'tag': clean_tag, 'stats': stats,
                'files_count': uploads_count}
        with zipfile.ZipFile(raw, 'a', zipfile.ZIP_DEFLATED) as inner:
            inner.writestr('metadata.json', json.dumps(meta))
            _safe_entries(inner)
        temporary = dest.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_STORED) as outer:
                outer.writestr('meta.json', json.dumps(meta))
                outer.writestr('payload.enc', _cipher().encrypt(raw.getvalue()))
            temporary.replace(dest)
        finally:
            temporary.unlink(missing_ok=True)
    rotate_backups()
    return {**meta, 'filename': filename, 'size_bytes': dest.stat().st_size,
            'human_size': human_size(dest.stat().st_size), 'uploads_count': uploads_count}


def create_backup(tag='manual'):
    from runtime import exclusive
    with exclusive():
        return _create_backup(tag)


def list_backups():
    out = []
    for path in config.BACKUPS_DIR.glob('ecogallo_backup_*.zip'):
        try:
            with zipfile.ZipFile(path) as zf:
                info = zf.getinfo('meta.json')
                if info.file_size > 65536:
                    continue
                meta = json.loads(zf.read('meta.json'))
            out.append({**meta, 'filename': path.name, 'size_bytes': path.stat().st_size,
                        'human_size': human_size(path.stat().st_size), 'uploads_count': meta.get('files_count', 0)})
        except (OSError, ValueError, zipfile.BadZipFile, KeyError):
            log.warning('Respaldo no reconocido: %s', path.name)
    return sorted(out, key=lambda b: b.get('created_timestamp', 0), reverse=True)


def get_backup_path(filename):
    if not isinstance(filename, str) or pathlib.Path(filename).name != filename or '/' in filename or '\\' in filename:
        return None
    if not filename.startswith('ecogallo_backup_') or not filename.endswith('.zip'):
        return None
    target = config.BACKUPS_DIR / filename
    if target.is_symlink():
        return None
    return target if target.is_file() else None


def delete_backup(filename):
    from runtime import exclusive
    with exclusive():
        path = get_backup_path(filename)
        if not path:
            return False
        path.unlink()
    return True


def save_uploaded_backup(file_storage):
    import uuid
    from runtime import exclusive
    with exclusive():
        path = config.BACKUPS_DIR / f'ecogallo_backup_{uuid.uuid4().hex}_subido.zip'
        try:
            file_storage.save(path)
            meta, _ = _read_backup(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        rotate_backups()
        return {**meta, 'filename': path.name, 'size_bytes': path.stat().st_size, 'human_size': human_size(path.stat().st_size)}


def restore_backup(filename, session_token=None, admin_user=None):
    import io
    import shutil
    from runtime import exclusive
    import db as dbmod
    with exclusive():
        if not config.UPLOADS.resolve().is_relative_to(config.DATA.resolve()) or not config.VERIF_DIR.resolve().is_relative_to(config.DATA.resolve()):
            raise ValueError("Los directorios de restauración deben permanecer dentro de ECOGALLO_DATA.")
        path = get_backup_path(filename)
        if not path:
            raise FileNotFoundError('Respaldo no encontrado.')
        meta, raw = _read_backup(path)
        with tempfile.TemporaryDirectory(dir=config.DATA) as tmp:
            stage = pathlib.Path(tmp)
            for prefix in ('uploads', 'verificaciones'):
                (stage / prefix).mkdir()
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for item in zf.infolist():
                    if item.is_dir():
                        continue
                    dest = (stage / item.filename).resolve()
                    if not dest.is_relative_to(stage.resolve()):
                        raise ValueError('Ruta de restauración no segura.')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(item))
            candidate = stage / 'database' / 'ecogallo.sqlite'
            con = sqlite3.connect(candidate)
            try:
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('La base de datos no superó las comprobaciones de integridad.')
                required = ('users', 'posts', 'orders', 'sessions', 'auth_challenges', 'stripe_webhook_events', 'post_images')
                for table in required:
                    con.execute(f'SELECT * FROM {table} LIMIT 0')  # nosec B608 - SQL structure from fixed constants; user values are bound parameters
                # Restoring an old snapshot over real financial activity can replay payouts.
                active = sqlite3.connect(config.DB_PATH)
                try:
                    if active.execute("SELECT 1 FROM orders WHERE payment_provider='stripe' LIMIT 1").fetchone():
                        raise ValueError('Hay historial de Stripe: la restauración requiere conciliación financiera fuera de línea.')
                finally:
                    active.close()
                if con.execute("SELECT 1 FROM orders WHERE payment_provider='stripe' LIMIT 1").fetchone():
                    raise ValueError('El respaldo tiene pagos Stripe. Usa la recuperación fuera de línea con conciliación financiera.')
                # Revoke snapshot sessions and grants; preserve only the requesting admin if still an admin.
                con.execute('DELETE FROM sessions')
                con.execute('DELETE FROM auth_challenges')
                con.execute('DELETE FROM login_codes')
                if session_token and admin_user:
                    from security import hash_token
                    admin = con.execute("SELECT id FROM users WHERE email=? AND role='admin' AND suspended=0", (admin_user['email'],)).fetchone()
                    if not admin:
                        raise ValueError('El administrador actual no existe en el respaldo.')
                    con.execute('INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)',
                                (hash_token(session_token), admin[0], int(time.time()), int(time.time()) + config.SESSION_DAYS * 86400))
                con.commit()
            except sqlite3.Error:
                raise ValueError('La estructura de la base de datos no es compatible.') from None
            finally:
                con.close()
            # Keep a durable undo snapshot and a local rollback copy before replacing anything.
            pre = _create_backup('pre_restore')
            dbmod.close_db()
            old_db = stage / 'rollback.sqlite'
            src = sqlite3.connect(config.DB_PATH)
            dst = sqlite3.connect(old_db)
            src.backup(dst)
            src.close()
            dst.close()
            swapped = []
            try:
                for live, prepared in ((config.UPLOADS, stage / 'uploads'), (config.VERIF_DIR, stage / 'verificaciones')):
                    rollback = stage / (live.name + '_rollback')
                    live.replace(rollback)
                    swapped.append((live, rollback))
                    prepared.replace(live)
                src = sqlite3.connect(candidate)
                dst = sqlite3.connect(config.DB_PATH)
                try:
                    src.backup(dst)
                finally:
                    src.close()
                    dst.close()
                dbmod.init_db()
            except BaseException:
                for live, rollback in reversed(swapped):
                    if live.exists():
                        shutil.rmtree(live)
                    rollback.replace(live)
                src = sqlite3.connect(old_db)
                dst = sqlite3.connect(config.DB_PATH)
                src.backup(dst)
                src.close()
                dst.close()
                raise
        return {'filename': filename, 'pre_backup': pre['filename'], 'stats': meta['stats'], 'uploads_restored': meta.get('files_count', 0)}


def start_backup_scheduler():
    """Inicia un hilo daemon en segundo plano que crea respaldos automáticos periódicos."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started or not config.BACKUP_ENABLED:
            return
        _scheduler_started = True

    def _worker():
        interval_secs = max(60.0, config.BACKUP_INTERVAL_HOURS * 3600.0)
        log.info(
            "Planificador de respaldos activo (intervalo: %s horas, retención: %s copias)",
            config.BACKUP_INTERVAL_HOURS,
            config.BACKUP_KEEP,
        )
        # Espera inicial para permitir que el servidor termine de iniciar
        time.sleep(15)

        while True:
            try:
                zips = sorted(
                    config.BACKUPS_DIR.glob("ecogallo_backup_*.zip"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                now_ts = time.time()
                should_run = False
                if not zips:
                    should_run = True
                else:
                    last_mtime = zips[0].stat().st_mtime
                    if now_ts - last_mtime >= interval_secs:
                        should_run = True

                if should_run:
                    log.info("Disparando respaldo periódico automático...")
                    create_backup(tag="auto")
            except Exception as e:
                log.exception("Error en ejecución del respaldo automático: %s", e)

            # Checar periódicamente cada 60 segundos
            time.sleep(60)

    t = threading.Thread(target=_worker, name="BackupScheduler", daemon=True)
    t.start()


if __name__ == "__main__":
    import sys
    print("=== ECO-GALLO UAA · Gestor de Respaldos ===")
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Uso: python backups.py restore <nombre_archivo.zip>")
            sys.exit(1)
        res = restore_backup(sys.argv[2])
        print(f"Restauración exitosa desde {res['filename']}")
        print(f"Copia preventiva creada: {res['pre_backup']}")
        print(f"Archivos restaurados en uploads: {res['uploads_restored']}")
        print(f"Estadísticas BD: {res['stats']}")
    else:
        tag = sys.argv[1] if len(sys.argv) > 1 else "cli"
        result = create_backup(tag=tag)
        print(f"Respaldo generado exitosamente: {result['filename']}")
        print(f"Tamaño: {result['human_size']}")
        print(f"Archivos en uploads: {result['uploads_count']}")
        print(f"Estadísticas BD: {result['stats']}")

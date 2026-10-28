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
import os
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


def create_backup(tag: str = "manual") -> dict:
    """Genera un archivo .zip con la base de datos y todas las imágenes.

    Devuelve un diccionario con los detalles del respaldo creado.
    """
    config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    now_dt = datetime.datetime.now()
    stamp = now_dt.strftime("%Y%m%d_%H%M%S")
    clean_tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_")) or "manual"
    filename = f"ecogallo_backup_{stamp}_{clean_tag}.zip"
    dest_path = config.BACKUPS_DIR / filename

    db_stats = {"users": 0, "posts": 0, "orders": 0}
    uploads_count = 0
    total_uncompressed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = pathlib.Path(tmpdir) / "ecogallo.sqlite"

        # 1. Copia segura y atómica de SQLite con sqlite3.backup
        if config.DB_PATH.exists():
            src = sqlite3.connect(config.DB_PATH)
            dst = sqlite3.connect(temp_db)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()

            # Leer estadísticas básicas desde la copia temporal
            try:
                con = sqlite3.connect(temp_db)
                cur = con.cursor()
                db_stats["users"] = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                db_stats["posts"] = cur.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
                db_stats["orders"] = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                con.close()
            except Exception as ex:
                log.warning("No se pudieron extraer estadísticas completas: %s", ex)

        # 2. Empaquetar en archivo ZIP comprimido
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if temp_db.exists():
                db_size = temp_db.stat().st_size
                total_uncompressed += db_size
                zf.write(temp_db, arcname="database/ecogallo.sqlite")

            # Respaldar fotos y avatares de uploads/
            if config.UPLOADS.exists():
                for f in config.UPLOADS.rglob("*"):
                    if f.is_file():
                        uploads_count += 1
                        total_uncompressed += f.stat().st_size
                        rel = f.relative_to(config.UPLOADS)
                        zf.write(f, arcname=f"uploads/{rel.as_posix()}")

            # Respaldar documentos privados de verificación si los hay
            if config.VERIF_DIR.exists():
                for f in config.VERIF_DIR.rglob("*"):
                    if f.is_file():
                        total_uncompressed += f.stat().st_size
                        rel = f.relative_to(config.VERIF_DIR)
                        zf.write(f, arcname=f"verificaciones/{rel.as_posix()}")

            # Metadatos del respaldo
            meta = {
                "system": "ECO-GALLO UAA",
                "version": "1.0",
                "created_at": now_dt.isoformat(),
                "created_timestamp": int(now_dt.timestamp()),
                "tag": clean_tag,
                "stats": db_stats,
                "files_count": uploads_count,
                "uncompressed_bytes": total_uncompressed,
            }
            meta_bytes = json.dumps(meta, indent=2, ensure_ascii=False).encode("utf-8")
            total_uncompressed += len(meta_bytes)
            zf.writestr("meta.json", meta_bytes)

    # 3. Aplicar rotación para no saturar el almacenamiento
    rotate_backups()

    size_bytes = dest_path.stat().st_size if dest_path.exists() else 0
    info = {
        "filename": filename,
        "size_bytes": size_bytes,
        "human_size": human_size(size_bytes),
        "created_at": now_dt.isoformat(),
        "created_timestamp": int(now_dt.timestamp()),
        "tag": clean_tag,
        "stats": db_stats,
        "uploads_count": uploads_count,
    }
    log.info("Respaldo creado con éxito: %s (%s)", filename, info["human_size"])
    return info


def list_backups() -> list[dict]:
    """Lista todos los respaldos existentes en config.BACKUPS_DIR."""
    config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in config.BACKUPS_DIR.glob("ecogallo_backup_*.zip"):
        try:
            st = p.stat()
            meta = {}
            with zipfile.ZipFile(p, "r") as zf:
                if "meta.json" in zf.namelist():
                    meta = json.loads(zf.read("meta.json").decode("utf-8"))
            out.append({
                "filename": p.name,
                "size_bytes": st.st_size,
                "human_size": human_size(st.st_size),
                "created_at": meta.get("created_at") or datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                "created_timestamp": meta.get("created_timestamp") or int(st.st_mtime),
                "tag": meta.get("tag", "manual"),
                "stats": meta.get("stats", {}),
                "uploads_count": meta.get("files_count", 0),
            })
        except Exception as e:
            log.warning("No se pudo leer respaldo %s: %s", p.name, e)
    out.sort(key=lambda b: b["created_timestamp"], reverse=True)
    return out


def get_backup_path(filename: str) -> pathlib.Path | None:
    """Valida y obtiene la ruta absoluta de un archivo de respaldo."""
    safe_name = pathlib.Path(filename).name
    if not safe_name.endswith(".zip") or not safe_name.startswith("ecogallo_backup_"):
        return None
    target = config.BACKUPS_DIR / safe_name
    return target if target.exists() and target.is_file() else None


def delete_backup(filename: str) -> bool:
    """Elimina un respaldo específico."""
    target = get_backup_path(filename)
    if not target:
        return False
    target.unlink(missing_ok=True)
    log.info("Respaldo eliminado manualmente: %s", filename)
    return True


def save_uploaded_backup(file_storage) -> dict:
    """Valida y guarda un archivo de respaldo .zip subido por un administrador."""
    config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    now_dt = datetime.datetime.now()
    stamp = now_dt.strftime("%Y%m%d_%H%M%S")
    clean_tag = "subido"
    filename = f"ecogallo_backup_{stamp}_{clean_tag}.zip"
    dest_path = config.BACKUPS_DIR / filename

    file_storage.save(dest_path)

    if not zipfile.is_zipfile(dest_path):
        dest_path.unlink(missing_ok=True)
        raise ValueError("El archivo subido no es un archivo .zip válido.")

    with zipfile.ZipFile(dest_path, "r") as zf:
        namelist = zf.namelist()
        if "database/ecogallo.sqlite" not in namelist:
            dest_path.unlink(missing_ok=True)
            raise ValueError("El archivo no contiene la base de datos de ECO-GALLO (database/ecogallo.sqlite).")

    rotate_backups()
    size_bytes = dest_path.stat().st_size
    info = {
        "filename": filename,
        "size_bytes": size_bytes,
        "human_size": human_size(size_bytes),
        "created_at": now_dt.isoformat(),
        "created_timestamp": int(now_dt.timestamp()),
        "tag": clean_tag,
    }
    log.info("Respaldo subido y validado exitosamente: %s", filename)
    return info


def restore_backup(filename: str, session_token: str | None = None, admin_user: dict | None = None) -> dict:
    """Restaura de forma atómica y consistente el sistema desde un archivo de respaldo .zip.

    1. Valida la integridad del archivo zip y previene ataques zip-slip.
    2. Comprueba la integridad de la base de datos SQLite antes de tocar los datos activos.
    3. Genera una copia preventiva del estado actual (tag: 'pre_restore').
    4. Sobrescribe la base de datos activa usando sqlite3.Connection.backup.
    5. Preserva la sesión del administrador para evitar desconexiones inesperadas.
    6. Restaura los directorios de archivos multimedia y documentos de verificación.
    """
    target = get_backup_path(filename)
    if not target:
        raise FileNotFoundError(f"Archivo de respaldo no encontrado: {filename}")

    if not zipfile.is_zipfile(target):
        raise ValueError("El archivo seleccionado no es un respaldo .zip válido.")

    with zipfile.ZipFile(target, "r") as zf:
        # Validación de seguridad: evitar path traversal (zip slip)
        for item in zf.infolist():
            path_parts = pathlib.PurePosixPath(item.filename).parts
            if pathlib.PurePosixPath(item.filename).is_absolute() or ".." in path_parts:
                raise ValueError(f"El respaldo contiene una ruta no segura: {item.filename}")

        if "database/ecogallo.sqlite" not in zf.namelist():
            raise ValueError("El respaldo no contiene la base de datos del sistema (database/ecogallo.sqlite).")

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = pathlib.Path(tmpdir) / "restore_eval.sqlite"
            temp_db.write_bytes(zf.read("database/ecogallo.sqlite"))

            # Validar integridad interna de SQLite
            con = sqlite3.connect(temp_db)
            try:
                cur = con.cursor()
                res = cur.execute("PRAGMA integrity_check").fetchall()
                if not res or res[0][0] != "ok":
                    raise ValueError("La base de datos del respaldo no superó la prueba de integridad SQLite.")
                tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                if "users" not in tables or "posts" not in tables:
                    raise ValueError("La base de datos del respaldo no contiene la estructura requerida de ECO-GALLO.")

                db_stats = {
                    "users": cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                    "posts": cur.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                    "orders": cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] if "orders" in tables else 0,
                }
            finally:
                con.close()

            # Paso preventivo: crear respaldo del estado actual
            pre_backup = create_backup(tag="pre_restore")
            log.info("Copia de seguridad preventiva generada antes de restaurar: %s", pre_backup["filename"])

            # Restaurar la base de datos SQLite en config.DB_PATH
            src_conn = sqlite3.connect(temp_db)
            dst_conn = sqlite3.connect(config.DB_PATH, timeout=30)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            # Preservar la sesión del administrador actual si se proporcionó
            if session_token and admin_user:
                try:
                    from security import hash_token
                    token_h = hash_token(session_token)
                    admin_conn = sqlite3.connect(config.DB_PATH)
                    try:
                        row = admin_conn.execute(
                            "SELECT id FROM users WHERE email=?", (admin_user.get("email"),)
                        ).fetchone()
                        if row:
                            uid = row[0]
                            now_t = int(time.time())
                            admin_conn.execute(
                                "INSERT OR REPLACE INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                                (token_h, uid, now_t, now_t + config.SESSION_DAYS * 86400),
                            )
                            admin_conn.commit()
                    finally:
                        admin_conn.close()
                except Exception as ex:
                    log.warning("No se pudo reinsertar la sesión del administrador: %s", ex)

            # Restaurar directorio de fotos (uploads/)
            config.UPLOADS.mkdir(parents=True, exist_ok=True)
            for p in config.UPLOADS.glob("*"):
                if p.is_file():
                    try:
                        p.unlink(missing_ok=True)
                    except OSError:
                        pass

            # Restaurar directorio de verificaciones privadas si existiera
            config.VERIF_DIR.mkdir(parents=True, exist_ok=True)
            for p in config.VERIF_DIR.glob("*"):
                if p.is_file():
                    try:
                        p.unlink(missing_ok=True)
                    except OSError:
                        pass

            uploads_restored = 0
            for item in zf.infolist():
                if item.is_dir():
                    continue
                parts = pathlib.PurePosixPath(item.filename).parts
                if not parts:
                    continue
                if parts[0] == "uploads" and len(parts) > 1:
                    dest = config.UPLOADS / pathlib.Path(*parts[1:])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(item.filename))
                    uploads_restored += 1
                elif parts[0] == "verificaciones" and len(parts) > 1:
                    dest = config.VERIF_DIR / pathlib.Path(*parts[1:])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(item.filename))

            # Ejecutar init_db para asegurar que migraciones y PRAGMAS queden activos
            import db as dbmod
            dbmod.init_db()

    log.info("Restauración completada con éxito desde %s", filename)
    return {
        "filename": filename,
        "pre_backup": pre_backup["filename"],
        "stats": db_stats,
        "uploads_restored": uploads_restored,
    }


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

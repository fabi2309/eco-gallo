"""Lee el archivo `.env` de la raíz del proyecto, si existe (sin dependencias externas).

Las variables que ya están en el entorno del proceso tienen prioridad: el archivo solo llena las que faltan.
Las líneas vacías, los comentarios (#) y los valores vacíos se ignoran, para que una plantilla a medio
llenar no borre los valores por defecto. No se lee durante las pruebas automáticas.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def load(path: Path | None = None) -> None:
    global _loaded
    if _loaded or "pytest" in sys.modules or os.environ.get("ECOGALLO_NO_DOTENV") == "1":
        return
    _loaded = True
    f = path or ROOT / ".env"
    if not f.is_file():
        return
    for raw in f.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip().removeprefix("export ").strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)

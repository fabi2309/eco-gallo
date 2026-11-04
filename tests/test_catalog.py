"""Pruebas sin servidor: integridad del catálogo UAA y validación de dominios institucionales.
Ejecutar:  python3 tests/test_catalog.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ECOGALLO_DATA", tempfile.mkdtemp(prefix="eg-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import catalog  # noqa: E402
import config  # noqa: E402
from security import is_institutional  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ok  " if ok else "FALLA ") + name)
    fails += 0 if ok else 1


todas = [c for lista in catalog.CENTROS_CARRERAS.values() for c in lista]
check("no hay carreras repetidas en el catálogo", len(todas) == len(set(todas)))
check("cada carrera pertenece a un solo centro", all(catalog.centro_de(c) for c in todas))
check("ninguna carrera ni centro está vacío", all(todas) and all(catalog.CENTROS_CARRERAS.values()))
check("los centros de publicación incluyen todos los del catálogo + General",
      set(catalog.CENTROS_CARRERAS) | {catalog.CENTRO_GENERAL} == set(catalog.CENTROS_POST))
check("nombres sin espacios sobrantes", all(c == c.strip() and "  " not in c for c in todas))

check("dominios configurados: edu.uaa.mx y alumnos.uaa.mx", set(config.EMAIL_DOMAINS) == {"edu.uaa.mx", "alumnos.uaa.mx"})
for ok in ["al350114@edu.uaa.mx", "al350114@alumnos.uaa.mx", "Ana.Lopez@EDU.UAA.MX".lower()]:
    check(f"acepta {ok}", is_institutional(ok))
for bad in ["alguien@gmail.com", "x@uaa.mx", "x@edu.uaa.mx.evil.com", "x@evil-edu.uaa.mx", "x@alumnos.uaa.mx.mx",
            "x@sub.edu.uaa.mx", "@edu.uaa.mx", "x y@edu.uaa.mx"]:
    check(f"rechaza {bad}", not is_institutional(bad))

print("\nTodo bien." if not fails else f"\n{fails} fallo(s).")
sys.exit(1 if fails else 0)

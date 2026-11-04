#!/usr/bin/env python3
"""Cruza backend/catalog.py con la oferta educativa publicada por la UAA.

Uso (en TU computadora, con internet):
    python tools/verificar_carreras.py                      # descarga el portal y compara
    python tools/verificar_carreras.py --archivo pagina.html   # compara contra una página guardada

Si el portal no permite lectura automática (robots.txt), el script no insiste: abre
https://www.uaa.mx/portal/oferta-educativa/licenciaturas/ en el navegador, guarda la página
(Ctrl+S, «Solo HTML») y usa --archivo.

Qué reporta:
  · EN CATÁLOGO, NO EN PORTAL  -> carreras que quizá cambiaron de nombre o ya no existen.
  · EN PORTAL, NO EN CATÁLOGO  -> carreras nuevas que faltan por agregar en catalog.py.
Sale con código 1 si hay diferencias (útil para revisarlo antes de cada semestre).
"""
import argparse
import html
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import os, tempfile  # noqa: E402
os.environ.setdefault("ECOGALLO_DATA", tempfile.mkdtemp(prefix="eg-cat-"))  # config crea carpetas al importarse
import catalog  # noqa: E402

URL = "https://www.uaa.mx/portal/oferta-educativa/licenciaturas/"
UA = "ECO-GALLO-verificador/1.0 (proyecto escolar UAA)"
# Encabezados típicos de una carrera en la UAA (para detectar candidatas que faltan en el catálogo).
CANDIDATA = re.compile(
    r"^(licenciatura en|licenciado en|ingenieria|ingeniero|medico|cirujano dentista|contador|arquitecto|"
    r"quimico|maestro|enfermeria|nutricion|psicologia|biologia|derecho|odontologia|medicina)\b")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", html.unescape(t).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


def descargar(url: str) -> str:
    rp = urllib.robotparser.RobotFileParser(url.split("/portal")[0] + "/robots.txt")
    try:
        rp.read()
        if not rp.can_fetch(UA, url):
            sys.exit("El portal no permite lectura automática (robots.txt).\n"
                     "Guarda la página desde tu navegador y ejecuta:  python tools/verificar_carreras.py --archivo pagina.html")
    except OSError:
        pass  # sin robots.txt accesible: seguimos con una sola petición educada
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"No se pudo descargar el portal ({e}). Usa --archivo con la página guardada.")


def lineas(htmltext: str) -> list[str]:
    htmltext = re.sub(r"(?is)<(script|style).*?</\1>", " ", htmltext)
    texto = re.sub(r"(?s)<[^>]+>", "\n", htmltext)
    return [re.sub(r"\s+", " ", html.unescape(l)).strip() for l in texto.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivo", help="HTML guardado de la página de licenciaturas")
    ap.add_argument("--url", default=URL)
    a = ap.parse_args()
    raw = Path(a.archivo).read_text("utf-8", "replace") if a.archivo else descargar(a.url)
    ls = lineas(raw)
    pagina = " | ".join(norm(l) for l in ls)

    en_catalogo = [(c, car) for c, lista in catalog.CENTROS_CARRERAS.items() for car in lista]
    faltan_en_portal = [(c, car) for c, car in en_catalogo if norm(car) not in pagina]

    conocidas = {norm(car) for _, car in en_catalogo}
    # Candidatas del portal: líneas cortas que parecen nombre de carrera y no están en el catálogo.
    nuevas = sorted({l for l in ls if 8 < len(l) < 90 and CANDIDATA.match(norm(l)) and norm(l) not in conocidas
                     and not any(norm(l) in k or k in norm(l) for k in conocidas)})

    print(f"Catálogo: {len(en_catalogo)} carreras en {len(catalog.CENTROS_CARRERAS)} centros. Página leída: {len(ls)} líneas de texto.\n")
    if not any(norm(car) in pagina for _, car in en_catalogo):
        print("⚠ Ninguna carrera del catálogo aparece en la página: puede que sea otra página o que se cargue con JavaScript.\n"
              "  Guarda la página ya cargada desde el navegador (Ctrl+S) y usa --archivo.")
        return 2
    print("EN CATÁLOGO, NO EN PORTAL (revisar nombre o si ya no existe):")
    print("\n".join(f"  - {car}   [{c}]" for c, car in faltan_en_portal) or "  (ninguna)")
    print("\nEN PORTAL, NO EN CATÁLOGO (posibles carreras por agregar):")
    print("\n".join(f"  + {n}" for n in nuevas) or "  (ninguna)")
    print("\nNota: el centro de cada carrera conviene confirmarlo en la ficha de la carrera en el portal.")
    return 1 if (faltan_en_portal or nuevas) else 0


if __name__ == "__main__":
    sys.exit(main())

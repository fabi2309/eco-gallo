"""ECO-GALLO UAA · Servidor de desarrollo local (100% Python, sin necesidad de Java).

Permite probar la aplicación completa (Frontend estático + API Flask + Base de datos)
directamente con Python cuando no se tiene Java JDK instalado.
"""
import os
import sys

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import config
from app import create_app
from flask import send_from_directory

app = create_app()

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    # Dejar que Flask maneje las rutas de /api y /uploads normalmente
    if path.startswith("api/") or path.startswith("uploads/"):
        return {"ok": False, "message": "No encontrado"}, 404

    target = os.path.join(FRONTEND_DIR, path)
    if path and os.path.isfile(target):
        return send_from_directory(FRONTEND_DIR, path)

    # Para cualquier otra ruta de la SPA, servir el index.html
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print("\n" + "=" * 60)
    print("  ECO-GALLO UAA · Servidor local de desarrollo (Python)")
    print(f"  Abre en tu navegador: http://localhost:{port}")
    print("  Presiona Ctrl+C para detener el servidor.")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=port, debug=True)

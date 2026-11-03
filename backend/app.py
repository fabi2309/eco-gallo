"""ECO-GALLO UAA · backend Flask (escucha solo en 127.0.0.1; el gateway Java es la puerta)."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, send_from_directory  # noqa: E402

import config  # noqa: E402
import db as dbmod  # noqa: E402
from security import load_user  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    dbmod.init_db()

    from admin import bp as admin_bp
    from auth import bp as auth_bp
    from orders import bp as orders_bp
    from posts import bp as posts_bp
    from social import bp as social_bp
    from wishlist import bp as wishlist_bp

    for bp in (auth_bp, posts_bp, orders_bp, social_bp, wishlist_bp, admin_bp):
        app.register_blueprint(bp)

    from backups import start_backup_scheduler
    start_backup_scheduler()

    app.before_request(load_user)
    app.teardown_appcontext(dbmod.close_db)

    @app.get("/uploads/<path:name>")
    def uploads(name):
        resp = send_from_directory(config.UPLOADS, name)
        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.errorhandler(404)
    def nf(_e):
        return jsonify({"ok": False, "message": "No encontrado."}), 404

    @app.errorhandler(405)
    def na(_e):
        return jsonify({"ok": False, "message": "Método no permitido."}), 405

    @app.errorhandler(413)
    def big(_e):
        return jsonify({"ok": False, "message": "El archivo es demasiado grande."}), 413

    @app.errorhandler(Exception)
    def boom(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"ok": False, "message": e.description}), e.code
        logging.getLogger("ecogallo").exception("Error no controlado")
        return jsonify({"ok": False, "message": "Error interno del servidor."}), 500

    if os.environ.get("ECOGALLO_SEED", "0") == "1":
        from seed import seed
        seed()
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("ECOGALLO_BACKEND_PORT", "5000"))
    # threaded: varias peticiones a la vez; SQLite WAL + BEGIN IMMEDIATE protege el escrow.
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)

"""Shared static frontend for local and production servers."""
from pathlib import Path

from flask import send_from_directory

from backend_path import setup_backend

setup_backend()
from app import app  # noqa: E402

FRONTEND = Path(__file__).resolve().parent / 'frontend'


@app.get('/', defaults={'path': ''})
@app.get('/<path:path>')
def frontend(path):
    if path.startswith(('api/', 'uploads/')):
        return {'ok': False, 'message': 'No encontrado.'}, 404
    target = (FRONTEND / path).resolve()
    if target.is_relative_to(FRONTEND) and target.is_file():
        return send_from_directory(FRONTEND, path)
    if '.' in path:
        return {'ok': False, 'message': 'No encontrado.'}, 404
    return send_from_directory(FRONTEND, 'index.html')

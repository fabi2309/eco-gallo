"""Bounded pagination shared by API lists."""
from flask import request


def pagination():
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('per_page', 100))
        if page < 1 or size < 1 or size > 100 or page > 1000000:
            raise ValueError
        return page, size, (page - 1) * size
    except (ValueError, TypeError):
        raise ValueError('Página o tamaño de página inválido.') from None

"""Production launcher: one process, concurrent Waitress threads, no debugger."""
import os

os.environ.setdefault('ECOGALLO_ENV', 'production')

from webapp import app  # noqa: E402
from waitress import serve  # noqa: E402

if __name__ == '__main__':
    serve(app, host=os.environ.get('ECOGALLO_BIND', '0.0.0.0'),
          port=int(os.environ.get('PORT', '8080')), threads=8,
          max_request_body_size=210 * 1024 * 1024, channel_timeout=60)

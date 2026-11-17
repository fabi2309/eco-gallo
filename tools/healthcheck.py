"""Check the internal HTTP listener while preserving the configured public Host."""
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

host = urlsplit(os.environ['ECOGALLO_PUBLIC_URL']).netloc
url = 'http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/health'
with urlopen(Request(url, headers={'Host': host}), timeout=3) as response:  # nosec B310 - fixed loopback HTTP endpoint
    if response.status != 200:
        raise SystemExit(1)

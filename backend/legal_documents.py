"""Plain-text counterparts of the web documents for accessible native reading."""
from html.parser import HTMLParser
import json
from pathlib import Path


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'h1', 'h2', 'li', 'br'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'h1', 'h2', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def documents(info):
    templates = json.loads(Path(__file__).with_name('legal_documents.json').read_text(encoding='utf-8'))
    values = {'name': info['operator'], 'addr': info['address'],
              'mail': info['email'] or '[correo de contacto pendiente de configurar]', 'version': info['version']}
    result = {}
    for name, template in templates.items():
        parser = PlainText()
        parser.feed(template)
        text = ''.join(parser.parts)
        for key, value in values.items():
            text = text.replace('${w.' + key + '}', value)
        result[name] = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    return result

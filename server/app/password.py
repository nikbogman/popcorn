"""Generates a new LOGIN_PASSWORD and writes it to server/.env, replacing the old one. Read it from .env; it isn't printed."""

import re
import secrets
from pathlib import Path

ENV = Path(__file__).parent.parent / '.env'

if __name__ == '__main__':
    line = f'LOGIN_PASSWORD={secrets.token_urlsafe(24)}'
    text = ENV.read_text(newline='') if ENV.exists() else ''
    text, replaced = re.subn(r'^LOGIN_PASSWORD=[^\r\n]*', lambda _: line, text, flags=re.M)
    if not replaced:
        text += ('' if text.endswith('\n') or not text else '\n') + line + '\n'
    ENV.write_text(text, newline='')
    print(f'Wrote a new LOGIN_PASSWORD to {ENV}. Tokens from the old one keep working until they expire.')

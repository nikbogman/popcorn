"""Generates a new LOGIN_PASSWORD and writes it to an .env file, replacing the old one. Read it from the file; it isn't printed.

Usage: python -m app.password [path/to/.env]   (default: server/.env)
"""

import re
import secrets
import sys
from pathlib import Path

ENV = Path(__file__).parent.parent / '.env'

if __name__ == '__main__':
    env = Path(sys.argv[1]) if len(sys.argv) > 1 else ENV
    line = f'LOGIN_PASSWORD={secrets.token_urlsafe(24)}'
    text = env.read_text(newline='') if env.exists() else ''
    text, replaced = re.subn(r'^LOGIN_PASSWORD=[^\r\n]*', lambda _: line, text, flags=re.M)
    if not replaced:
        text += ('' if text.endswith('\n') or not text else '\n') + line + '\n'
    # Owner-only before the password goes in. On Windows chmod only toggles read-only.
    env.touch(mode=0o600)
    env.chmod(0o600)
    env.write_text(text, newline='')
    print(f'Wrote a new LOGIN_PASSWORD to {env}. Tokens from the old one keep working until they expire.')

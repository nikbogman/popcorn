import os
import subprocess
import sys


def test_rewrites_only_the_password_in_an_owner_only_file(tmp_path):
    env = tmp_path / '.env'
    env.write_text('A=1\nLOGIN_PASSWORD=old\nB=2\n')
    out = subprocess.run([sys.executable, '-m', 'app.password', str(env)], capture_output=True, text=True, check=True).stdout
    lines = env.read_text().splitlines()
    assert lines[0] == 'A=1' and lines[2] == 'B=2'
    password = lines[1].removeprefix('LOGIN_PASSWORD=')
    assert len(password) > 20 and password != 'old'
    assert password not in out
    if os.name == 'posix':
        assert env.stat().st_mode & 0o777 == 0o600


def test_creates_the_file(tmp_path):
    env = tmp_path / 'stacks' / '.env'
    env.parent.mkdir()
    subprocess.run([sys.executable, '-m', 'app.password', str(env)], check=True, capture_output=True)
    assert env.read_text().startswith('LOGIN_PASSWORD=')

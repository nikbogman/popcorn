import os


def env(*names: str):
    """The named variables from the environment. Raises naming every one that is unset or empty."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f'Set {", ".join(missing)} in the environment or server/.env')
    return {n: os.environ[n] for n in names}

import os


def env(*names: str) -> list[str]:
    """The named variables' values, in order. Exits naming every one that is unset or empty."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f'Set {", ".join(missing)} in the environment or server/.env')
    return [os.environ[n] for n in names]

"""Read server-only configuration from .env.local, matching .env.example.

The Node server used `node --env-file-if-exists=.env.local`; Django has no
equivalent, so the same file is parsed here. Real environment variables win, so
a host can inject configuration without editing files.
"""

from pathlib import Path

_CACHE = None


def _load(base_dir: Path) -> dict:
    values = {}
    for name in (".env.example", ".env.local"):
        path = base_dir / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if value:
                values[key.strip()] = value
    return values


def load(base_dir: Path) -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load(base_dir)
    return _CACHE


def get(base_dir: Path, key: str, default: str = "") -> str:
    import os

    if key in os.environ:
        return os.environ[key]
    return load(base_dir).get(key, default)


def flag(base_dir: Path, key: str, default: bool) -> bool:
    raw = get(base_dir, key, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

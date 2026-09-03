"""Minimal .env loading.

Deliberately dependency-free. In Docker the process gets real environment
variables and the .env file simply will not exist, so this is a no-op there.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path=None):
    """Load KEY=VALUE lines from .env without overriding the real environment."""
    path = Path(path) if path else REPO_ROOT / ".env"
    if not path.exists():
        return False
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    return True

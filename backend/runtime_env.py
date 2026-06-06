"""Shared dotenv bootstrap for all backend execution paths.

Some code paths (scripts/tests/direct imports) do not pass through
`app.main`, so relying on FastAPI startup alone can leave `os.environ`
missing keys from `backend/.env` during runtime smoke or node execution.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ensure_env_loaded() -> Path:
    backend_dir = Path(__file__).resolve().parent
    env_path = backend_dir / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception:
        # Keep runtime resilient when python-dotenv is unavailable.
        pass
    return env_path


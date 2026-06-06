"""Write workflow export files under DBSHERPA_OUTPUT_DIR for Studio downloads."""
from __future__ import annotations

import os
import re
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def output_dir() -> Path:
    root = os.environ.get("DBSHERPA_OUTPUT_DIR")
    path = Path(root) if root else _BACKEND_ROOT / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, default: str = "output.csv") -> str:
    base = Path(name).name or default
    if not re.match(r"^[A-Za-z0-9._-]+$", base):
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", base) or default
    return base


def write_export_file(filename: str, content: bytes, *, default_name: str = "output.csv") -> tuple[Path, str]:
    """Persist bytes and return (absolute path, download URL path)."""
    safe = safe_filename(filename, default_name)
    path = output_dir() / safe
    path.write_bytes(content)
    return path, f"/report/{safe}"

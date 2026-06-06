from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TruncationResult:
    preview: str
    full_path: str | None
    truncated: bool
    byte_size: int


def truncate_with_spillover(
    text: str,
    *,
    output_dir: Path,
    max_lines: int = 120,
    max_bytes: int = 16000,
) -> TruncationResult:
    raw = text or ""
    byte_size = len(raw.encode("utf-8"))
    lines = raw.splitlines()
    should_truncate = len(lines) > max_lines or byte_size > max_bytes
    if not should_truncate:
        return TruncationResult(preview=raw, full_path=None, truncated=False, byte_size=byte_size)

    preview_lines = lines[:max_lines]
    preview = "\n".join(preview_lines)
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    path = output_dir / f"tool_output_{digest}.txt"
    path.write_text(raw, encoding="utf-8")
    hint = f"\n\n[truncated] Full output saved to: {path}"
    return TruncationResult(
        preview=(preview + hint).strip(),
        full_path=str(path),
        truncated=True,
        byte_size=byte_size,
    )

from __future__ import annotations

from pathlib import Path

from generation.harness.output_truncation import truncate_with_spillover


def test_small_output_not_truncated(tmp_path: Path) -> None:
    result = truncate_with_spillover("hello", output_dir=tmp_path, max_lines=10, max_bytes=100)
    assert result.truncated is False
    assert result.full_path is None
    assert result.preview == "hello"


def test_large_output_spills_to_file(tmp_path: Path) -> None:
    text = "\n".join(f"line {i}" for i in range(300))
    result = truncate_with_spillover(text, output_dir=tmp_path, max_lines=20, max_bytes=2000)
    assert result.truncated is True
    assert result.full_path is not None
    assert "[truncated]" in result.preview
    assert Path(result.full_path).is_file()

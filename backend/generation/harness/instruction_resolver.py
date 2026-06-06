from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstructionResolver:
    global_file: Path | None = None
    project_root: Path | None = None
    _seen_in_cycle: set[str] = field(default_factory=set, init=False, repr=False)

    def begin_cycle(self) -> None:
        self._seen_in_cycle.clear()

    def resolve(self, around_paths: list[Path] | None = None) -> list[str]:
        out: list[str] = []
        candidates: list[Path] = []

        if self.global_file and self.global_file.is_file():
            candidates.append(self.global_file)

        root = self.project_root
        if root and root.is_dir():
            for name in ("AGENTS.md", "RULES.md", ".instructions.md"):
                p = root / name
                if p.is_file():
                    candidates.append(p)

        for path in around_paths or []:
            p = Path(path)
            if p.is_file():
                p = p.parent
            for name in ("AGENTS.md", ".instructions.md"):
                q = p / name
                if q.is_file():
                    candidates.append(q)

        for c in candidates:
            key = str(c.resolve())
            if key in self._seen_in_cycle:
                continue
            try:
                text = c.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if not text:
                continue
            self._seen_in_cycle.add(key)
            out.append(f"[{c.name}]\n{text}")
        return out

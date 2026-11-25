"""Paths, run ids and hashing shared by every stage."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def canonical(obj) -> str:
    """JSON with sorted keys and no whitespace, so a cache key is identical on every OS (ADR-004)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Workspace:
    """Where a run writes. Real runs use the repo root; mock runs use build/mock/ (ADR-016)."""

    root: Path
    base: Path
    mock: bool
    run_id: str

    @classmethod
    def create(cls, root: Path, mock: bool = False) -> "Workspace":
        root = root.resolve()
        base = root / "build" / "mock" if mock else root
        (base / "outputs").mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return cls(root=root, base=base, mock=mock, run_id=f"r-{stamp}-{secrets.token_hex(2)}")

    @property
    def outputs(self) -> Path:
        return self.base / "outputs"

    @property
    def runs_log(self) -> Path:
        return self.base / "runs.jsonl"

    @property
    def stages_log(self) -> Path:
        return self.base / "stages.jsonl"

    def rel(self, path: Path) -> str:
        """A path relative to the repo root in POSIX form, for logs and timelines."""
        return Path(path).resolve().relative_to(self.root).as_posix()

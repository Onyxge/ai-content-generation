"""Logs (ADR-007). runs.jsonl gets one line per model-call attempt; stages.jsonl gets one
line per stage per run, plus the assembly measurements."""
from __future__ import annotations

import json
from pathlib import Path

from .workspace import Workspace, utc_now


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RunLog:
    def __init__(self, ws: Workspace):
        self.ws = ws

    def model_call(self, **fields) -> dict:
        record = {"ts": utc_now(), "run_id": self.ws.run_id, **fields}
        append_jsonl(self.ws.runs_log, record)
        return record

    def stage(self, **fields) -> dict:
        record = {"ts": utc_now(), "run_id": self.ws.run_id, **fields}
        append_jsonl(self.ws.stages_log, record)
        return record

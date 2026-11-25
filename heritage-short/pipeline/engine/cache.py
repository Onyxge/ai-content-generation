"""Per-unit content-hash cache with sidecar files (ADR-004).

A unit's key is the sha256 of canonical JSON describing everything that determines its
output. The key and the artifact's own hash live in a sidecar next to the artifact
(`s04.png.json`). A unit is fresh when the sidecar key matches and the file is unchanged."""
from __future__ import annotations

import json
from pathlib import Path

from .workspace import canonical, sha256_file, sha256_text


def unit_key(material: dict) -> str:
    return sha256_text(canonical(material))


def sidecar(artifact: Path) -> Path:
    return artifact.with_name(artifact.name + ".json")


def read_sidecar(artifact: Path) -> dict | None:
    path = sidecar(artifact)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def is_fresh(artifact: Path, key: str) -> bool:
    meta = read_sidecar(artifact)
    return bool(meta and meta.get("cache_key") == key and artifact.exists()
                and sha256_file(artifact) == meta.get("output_sha"))


def write_sidecar(artifact: Path, key: str, info: dict) -> dict:
    meta = {"cache_key": key, "output_sha": sha256_file(artifact), **info}
    sidecar(artifact).write_text(json.dumps(meta, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    return meta

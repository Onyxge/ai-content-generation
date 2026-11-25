"""Pipeline settings that are not part of the story (config/pipeline.toml)."""
from __future__ import annotations

import tomllib
from pathlib import Path


def load_config(root: Path) -> dict:
    with open(root / "config" / "pipeline.toml", "rb") as f:
        return tomllib.load(f)

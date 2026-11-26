import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent


@pytest.fixture
def storyboard() -> dict:
    return json.loads((FIXTURES / "storyboard.example.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_root(tmp_path: Path) -> Path:
    """A throwaway repo root: test config, the real agent policy, the example storyboard and an empty ETHICS.md."""
    (tmp_path / "config").mkdir()
    shutil.copy(FIXTURES / "pipeline.test.toml", tmp_path / "config" / "pipeline.toml")
    shutil.copy(REPO / "config" / "agents.toml", tmp_path / "config" / "agents.toml")
    shutil.copy(FIXTURES / "storyboard.example.json", tmp_path / "storyboard.json")
    (tmp_path / "ETHICS.md").write_text("# Ethics\n", encoding="utf-8")
    return tmp_path

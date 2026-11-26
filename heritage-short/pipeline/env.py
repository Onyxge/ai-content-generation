"""Keys come from the environment or from `.env` at the repo root, which is gitignored
(non-negotiable 7). Values already in the environment win. Nothing here ever prints a value."""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(root: Path) -> list[str]:
    """Read KEY=VALUE lines from <root>/.env into os.environ; return the names it set."""
    path = Path(root) / ".env"
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip().removeprefix("export ").strip(), value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded


def need(*names: str) -> dict[str, str]:
    """The named variables, or a RuntimeError that lists the missing ones (never their values)."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing {', '.join(missing)}: add {'it' if len(missing) == 1 else 'them'} to .env "
                           "(see .env.example)")
    return {n: os.environ[n] for n in names}

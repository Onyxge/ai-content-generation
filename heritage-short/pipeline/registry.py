"""The rendering stages in dependency order. `make film`, `film plan` and the price of a
proposal (ADR-018) all evaluate this same list."""
from __future__ import annotations

from .keyframes import Keyframes
from .music import Music
from .narration import Narration
from .references import References
from .shots import Shots

STAGES = (References, Keyframes, Narration, Music, Shots)


def stages():
    return [cls() for cls in STAGES]

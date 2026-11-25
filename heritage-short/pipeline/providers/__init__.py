"""Providers: thin adapters chosen by mode and config (01-plan §3).

Mock providers make labelled placeholders so the whole pipeline runs offline. Real
providers are unit U3; until then `Unavailable` stands in, so a cache hit never needs
them and a miss gets a clear message instead of a crash."""
from __future__ import annotations

from ..engine.retry import ProviderUnavailable
from .mock import MockImage, MockMusic, MockSpeech, MockVideo


class Unavailable:
    def __init__(self, name: str, model: str, why: str, pending: bool = False):
        self.name, self.model, self.why, self.pending = name, model, why, pending

    def _raise(self, **_):
        raise ProviderUnavailable(self.why, pending=self.pending)

    generate = speak = compose = animate = _raise


def load(cfg: dict, mock: bool) -> dict:
    if mock:
        return {"image": MockImage(), "speech": MockSpeech(), "music": MockMusic(), "video": MockVideo()}
    return {
        "image": Unavailable("cloudflare", cfg["images"]["model"],
                             "the real image provider is unit U3 and isn't built yet"),
        "speech": Unavailable("gemini", "per-voice",
                              "the real speech provider is unit U3 and isn't built yet"),
        "music": Unavailable("gpu-runner", cfg["music"]["model"],
                             "music runs on the GPU runner: `film bundle music`, then `film ingest` (U3)", pending=True),
        "video": Unavailable("gpu-runner", cfg["video"]["i2v_model"],
                             "clips run on the GPU runner: `film bundle shots`, then `film ingest` (U3)", pending=True),
    }

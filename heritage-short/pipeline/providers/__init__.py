"""Providers: thin adapters chosen by mode and config (01-plan §3).

Mock providers make labelled placeholders so the whole pipeline runs offline. Real
providers need keys in .env; when a key is missing, `Unavailable` stands in, so a cache hit
never needs it and a miss gets a clear message instead of a crash. Music and clips run on
the GPU runner, so locally they are always pending until `film ingest` brings them in."""
from __future__ import annotations

import os

from ..engine.retry import ProviderUnavailable
from .mock import MockImage, MockMusic, MockSpeech, MockText, MockVideo


class Unavailable:
    def __init__(self, name: str, model: str, why: str, pending: bool = False):
        self.name, self.model, self.why, self.pending = name, model, why, pending

    def _raise(self, **_):
        raise ProviderUnavailable(self.why, pending=self.pending)

    generate = speak = compose = animate = generate_json = _raise


class SpeechRouter:
    """Narration goes to whichever provider the voice names (ADR-015): a voice whose model is
    `addis-voices-2` is spoken by Addis AI, any other by Gemini. Swapping the Amharic voice is a
    Y edit to storyboard.json, and the cache regenerates only that language's lines. The log
    records the provider that actually spoke each line."""

    name, model = "speech", "per-voice"

    def __init__(self, gemini, addis):
        self.gemini, self.addis = gemini, addis

    def speak(self, *, text: str, lang: str, voice: dict, out) -> dict:
        from ..engine.retry import ProviderError

        target = self.addis if str(voice.get("model", "")).startswith("addis") else self.gemini
        try:
            if target is self.addis:
                from ..engine.workspace import canonical, sha256_text
                request_id = "hs-" + sha256_text(canonical({"text": text, "lang": lang, "voice": voice}))[:24]
                return target.speak(text=text, lang=lang, voice=voice, out=out, request_id=request_id)
            return target.speak(text=text, lang=lang, voice=voice, out=out)
        except ProviderError as e:
            e.provider = target.name                  # so a failed attempt is logged against who failed
            raise


def _missing(*names: str) -> str:
    gone = [n for n in names if not os.environ.get(n)]
    return f"add {', '.join(gone)} to .env (see .env.example)" if gone else ""


def load(cfg: dict, mock: bool) -> dict:
    if mock:
        return {"image": MockImage(), "speech": MockSpeech(), "music": MockMusic(), "video": MockVideo(),
                "text": MockText(), "text_lite": MockText()}
    from .addis import AddisSpeech
    from .cloudflare import CloudflareImage
    from .gemini import GeminiSpeech, GeminiText

    gemini_missing = _missing("GEMINI_API_KEY")
    cf_missing = _missing("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
    addis_missing = _missing("ADDIS_AI_API_KEY")
    text_cfg = cfg.get("text", {})
    return {
        "image": (Unavailable("cloudflare", cfg["images"]["model"], cf_missing) if cf_missing
                  else CloudflareImage(cfg["images"]["model"], cfg["images"].get("reference_upload_max", 504))),
        "speech": SpeechRouter(
            Unavailable("gemini", "per-voice", gemini_missing) if gemini_missing else GeminiSpeech(),
            Unavailable("addis", "addis-voices-2", addis_missing) if addis_missing else AddisSpeech()),
        "text": (Unavailable("gemini", text_cfg.get("model", "?"), gemini_missing) if gemini_missing
                 else GeminiText(text_cfg["model"])),
        "text_lite": (Unavailable("gemini", text_cfg.get("lite_model", "?"), gemini_missing) if gemini_missing
                      else GeminiText(text_cfg["lite_model"])),
        "music": Unavailable("gpu-runner", cfg["music"]["model"],
                             "music runs on the GPU runner: `film bundle music`, then `film ingest`", pending=True),
        "video": Unavailable("gpu-runner", cfg["video"]["i2v_model"],
                             "clips run on the GPU runner: `film bundle shots`, then `film ingest`", pending=True),
    }

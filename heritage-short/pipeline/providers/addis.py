"""Addis AI adapter: Addis Voices 2, a speech model built for Amharic (and Afaan Oromo,
Tigrinya and others), as a second Amharic narrator next to Gemini TTS (E21).

Docs checked 2026-11-25 (docs.addisassistant.com and the official `addisai` SDK):
- POST https://api.addisassistant.com/api/v1/voice/generations, header `x-api-key`, JSON
  {text, voice_id, language, output_format, client_request_id, voice_settings: {speed}}.
- The answer is JSON whose `data` holds the audio. Production answers 201 Created with the WAV
  inline as a data: URL in `data.audio` (seen in our first smoke test, FAILURES.md F4); the docs
  describe a signed, expiring `audio_url` instead, fetched with a second GET, without the key.
  We accept either.
- Billing is pay-as-you-go in ETB (5 ETB a generated minute); 402 means the credit ran out,
  429 means the model is at capacity, 409 GENERATION_IN_PROGRESS means wait and retry with
  the same client_request_id. There are no daily quotas.
- English isn't one of its languages, so English narration stays on Gemini.

Its Terms (2026-07-13) let Addis AI use what we send to train models, whatever the FAQ says,
so only the film's own narration goes there: nothing from private/ (ETHICS.md)."""
from __future__ import annotations

import base64
import re
import subprocess
import tempfile
from pathlib import Path

from ..engine.retry import BadRequestError, DailyQuotaError, ProviderError, SafetyBlockError, TransientError
from ..env import need

BASE = "https://api.addisassistant.com"
MODEL = "addis-voices-2"
LANGUAGES = {"am", "om", "ti", "sw", "ha", "sid", "wal"}
TIMEOUT_S = 95                                    # the SDK's own minimum for a generation


class AddisSpeech:
    name = "addis"
    model = MODEL

    def speak(self, *, text: str, lang: str, voice: dict, out: Path, request_id: str = "") -> dict:
        import requests

        if lang not in LANGUAGES:
            raise BadRequestError(f"Addis Voices 2 doesn't speak '{lang}'; use a Gemini voice for it")
        key = need("ADDIS_AI_API_KEY")["ADDIS_AI_API_KEY"]
        body = {"text": text, "voice_id": voice["voice"], "language": lang, "output_format": "wav_44100",
                "voice_settings": {"speed": float(voice.get("speed", 1.0))}, "stream": False}
        if request_id:
            body["client_request_id"] = request_id     # the same id on a retry, so it isn't billed twice
        try:
            resp = requests.post(f"{BASE}/api/v1/voice/generations", json=body, timeout=TIMEOUT_S,
                                 headers={"x-api-key": key, "Accept": "application/json"})
        except requests.Timeout as e:
            raise TransientError("Addis AI timed out") from e
        except requests.ConnectionError as e:
            raise TransientError("Addis AI connection failed") from e
        if not 200 <= resp.status_code < 300:              # a new clip comes back as 201 Created
            raise classify(resp.status_code, resp.text, resp.headers.get("Retry-After"))
        data = resp.json().get("data") or {}
        url = (data.get("audio") or data.get("audio_url") or data.get("audio_data_url")
               or (data.get("playback") or {}).get("url"))
        if not url:
            raise BadRequestError(f"Addis AI returned no audio; data keys were {sorted(data)}")
        if url.startswith("data:"):
            audio = base64.b64decode(url.split(",", 1)[1])
        else:
            got = requests.get(url, timeout=60)        # a signed URL: never send the key here
            if got.status_code != 200:
                raise TransientError(f"Addis AI audio download failed: {got.status_code}")
            audio = got.content
        to_wav(audio, out)
        usage = resp.json().get("usage") or {}
        return {"provider": self.name, "model": MODEL,
                "params": {"voice": voice["voice"], "lang": lang, "speed": body["voice_settings"]["speed"],
                           "format": data.get("output_format", "wav_44100"),
                           "duration_s": data.get("duration_seconds"), "clip_id": data.get("id")},
                "cost": {"credits_used": usage.get("credits_used"), "currency": usage.get("currency", "ETB"),
                         "credits_remaining": usage.get("credits_remaining")}}


def to_wav(audio: bytes, out: Path) -> None:
    """Keep a WAV as it is; convert anything else (mp3, say) with FFmpeg."""
    if audio[:4] == b"RIFF":
        Path(out).write_bytes(audio)
        return
    from .. import media

    with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
        tmp.write(audio)
        tmp.flush()
        try:
            media.ffmpeg(["-i", tmp.name, "-f", "wav", str(out)])
        except subprocess.CalledProcessError as e:
            raise BadRequestError(f"Addis AI audio couldn't be decoded: {(e.stderr or '')[-200:]}") from e


def classify(status: int, body: str, retry_after: str | None = None) -> ProviderError:
    text = body or ""
    code = re.search(r'"code"\s*:\s*"([^"]+)"', text)
    code = code.group(1) if code else ""
    wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else None
    if status == 402 or code.lower() in ("balance_too_low", "insufficient_credits"):
        return DailyQuotaError(f"Addis AI credit used up ({code or status}); top up the wallet")
    if status in (429, 503) or code.upper() in ("LANGUAGE_CAPACITY_REACHED", "GENERATION_IN_PROGRESS"):
        return TransientError(f"Addis AI busy ({code or status})", retry_after=wait)
    if status == 409:
        return TransientError(f"Addis AI conflict ({code})", retry_after=wait)
    if status >= 500:
        return TransientError(f"Addis AI {status}")
    if re.search(r"safety|moderation|blocked", text, re.IGNORECASE):
        return SafetyBlockError(f"Addis AI refused the text: {text[:200]}")
    if status in (400, 401, 403, 404, 413, 422):
        return BadRequestError(f"Addis AI {status} {code}: {text[:300]}")
    return ProviderError(f"Addis AI {status} {code}: {text[:300]}")

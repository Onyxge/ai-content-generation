"""Gemini adapters (unit U3): structured text and vision for the agents, and speech for
narration. Every failure is mapped to one of the engine's error classes, so the runner can
retry, defer or carry on (01-plan §8). Keys come from .env and are never logged."""
from __future__ import annotations

import io
import json
import re
import wave
from pathlib import Path

from ..contract import json_problems
from ..engine.retry import (BadRequestError, DailyQuotaError, ProviderError, RepairableError,
                            SafetyBlockError, TransientError)
from ..env import need

# 3.8 TTS returns a complete WAV (24 kHz, mono, 16-bit) from a one-shot call; older and streamed
# responses are headerless PCM at the same rate, which write_wav wraps.
PCM_RATE, PCM_WIDTH, PCM_CHANNELS = 24000, 2, 1
# A 429 whose quotaId says PerDay is the daily cap: retryDelay means nothing there, so stop until
# the reset (midnight Pacific, 11:00 EAT). Anything else (PerMinute, rate_limit_exceeded) is retried.
DAILY = re.compile(r"PerDay", re.IGNORECASE)
TIMEOUT_MS = 240_000


def _client():
    """v1beta, because the 3.8 TTS models need it; the SDK's own retries are off, because the
    engine retries and must log every attempt (non-negotiable 5); and a 240 s timeout, because
    the first smoke test waited 131 s for a 9-token answer while the model was overloaded
    (FAILURES.md F3), and a call that hangs past that should become a logged, retried attempt."""
    from google import genai                         # imported lazily: a clean clone rebuilds without it
    from google.genai import types

    return genai.Client(api_key=need("GEMINI_API_KEY")["GEMINI_API_KEY"],
                        http_options=types.HttpOptions(api_version="v1beta", timeout=TIMEOUT_MS,
                                                       retry_options=types.HttpRetryOptions(attempts=1)))


def map_error(e: Exception) -> ProviderError:
    """Turn an SDK or network error into an engine error. Daily caps and per-minute limits both
    arrive as 429; the quota id in the body tells them apart (…PerDay… vs …PerMinute…)."""
    from google.genai import errors

    if isinstance(e, errors.APIError):
        body = json.dumps(e.details, ensure_ascii=False) if e.details is not None else str(e)
        if e.code == 429:
            if DAILY.search(body) or "quota_exceeded" in body:
                cap = re.search(r'"quotaValue"\s*:\s*"?(\d+)', body)
                return DailyQuotaError(f"Gemini daily quota used up: {_quota_id(body)}"
                                       + (f" (cap {cap.group(1)} a day)" if cap else " (cap not stated)"),
                                       cap=int(cap.group(1)) if cap else None)
            delay = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
            return TransientError(f"Gemini rate limit: {_quota_id(body)}",
                                  retry_after=float(delay.group(1)) if delay else None)
        if e.code in (500, 502, 503, 504):
            return TransientError(f"Gemini {e.code} {e.status}")
        if e.code in (400, 404):
            return BadRequestError(f"Gemini {e.code} {e.status}: {e.message}")
        return ProviderError(f"Gemini {e.code} {e.status}: {e.message}")
    if e.__class__.__name__ in ("TimeoutException", "ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError"):
        return TransientError(f"Gemini network error: {e.__class__.__name__}")
    return ProviderError(f"Gemini: {e.__class__.__name__}: {e}")


def _quota_id(body: str) -> str:
    m = re.search(r'"quotaId"\s*:\s*"([^"]+)"', body)
    return m.group(1) if m else "see the error body in runs.jsonl"


def _blocked(resp) -> str | None:
    feedback = getattr(resp, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        return str(feedback.block_reason)
    for c in getattr(resp, "candidates", None) or []:
        reason = str(getattr(c, "finish_reason", "") or "")
        if any(word in reason for word in ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII", "IMAGE_SAFETY")):
            return reason
    return None


# Gemini drops some JSON Schema keywords without saying so (pattern, minLength, maxLength,
# uniqueItems…), so every structured answer is validated before anyone uses it.
schema_problems = json_problems


class GeminiText:
    """Structured output, optionally over images: the story chain, look-dev and the critic."""

    name = "gemini"

    def __init__(self, model: str):
        self.model = model
        self._c = None

    @property
    def client(self):
        if self._c is None:
            self._c = _client()
        return self._c

    def generate_json(self, *, prompt: str, schema: dict, system: str = "", images: list[Path] = (),
                      temperature: float = 0.4) -> tuple[dict, dict]:
        """Return (parsed JSON, log info). The schema constrains the output; images ride along as PNGs."""
        from google.genai import types

        parts = [types.Part.from_bytes(data=Path(p).read_bytes(), mime_type=_mime(p)) for p in images]
        parts.append(types.Part.from_text(text=prompt))
        config = types.GenerateContentConfig(
            system_instruction=system or None, temperature=temperature,
            response_mime_type="application/json", response_json_schema=schema)
        try:
            resp = self.client.models.generate_content(model=self.model, contents=parts, config=config)
        except Exception as e:                     # noqa: BLE001 - every failure is classified below
            raise map_error(e) from e
        if (why := _blocked(resp)) is not None:
            raise SafetyBlockError(f"Gemini blocked the request: {why}")
        text = resp.text or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise RepairableError([f"the answer wasn't valid JSON: {text[:200]!r}"]) from None
        problems = schema_problems(data, schema)
        if problems:
            err = RepairableError([f"schema: {p}" for p in problems[:8]])
            err.answer = data
            raise err
        usage = getattr(resp, "usage_metadata", None)
        # temperature is sent but Gemini 3.6+ ignores sampling settings; logged so the record is honest
        return data, {"model": self.model,
                      "params": {"temperature": temperature, "images": len(images),
                                 "tokens_in": getattr(usage, "prompt_token_count", None),
                                 "tokens_out": getattr(usage, "candidates_token_count", None)}}


class GeminiSpeech:
    """Narration: one WAV per line. Only the spoken words go in as text (non-negotiable:
    Gemini TTS reads its text verbatim); the voice, the language and the style instruction
    travel in their own fields."""

    name = "gemini"
    model = "per-voice"                               # each voice in storyboard.json names its own model

    def __init__(self):
        self._c = None

    @property
    def client(self):
        if self._c is None:
            self._c = _client()
        return self._c

    def speak(self, *, text: str, lang: str, voice: dict, out: Path) -> dict:
        from google.genai import types

        # The style rides on the part as speech metadata, never in the text, which 3.8 TTS speaks
        # verbatim. No language_code: Amharic isn't one of its allowed values, and the model
        # detects the language from the text.
        part = types.Part(text=text, speech_metadata=types.SpeechMetadata(style=voice["style"])
                          if voice.get("style") else None)
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(voice=voice["voice"])))
        try:
            resp = self.client.models.generate_content(
                model=voice["model"], contents=[types.Content(role="user", parts=[part])], config=config)
        except Exception as e:                     # noqa: BLE001
            raise map_error(e) from e
        if (why := _blocked(resp)) is not None:
            raise SafetyBlockError(f"Gemini blocked the line: {why}")
        try:
            blob = resp.candidates[0].content.parts[0].inline_data
        except (AttributeError, IndexError, TypeError) as e:
            raise BadRequestError("Gemini returned no audio for this line") from e
        write_wav(blob.data, blob.mime_type or "", out)
        return {"provider": self.name, "model": voice["model"], "params": {"voice": voice["voice"], "lang": lang,
                                                    "style": voice.get("style", ""), "mime": blob.mime_type}}


def write_wav(data: bytes, mime: str, out: Path) -> None:
    """Write audio bytes as WAV. Bytes that already carry a RIFF header are written as they are;
    raw PCM is wrapped, using the rate the mime type states (e.g. audio/L16;rate=24000)."""
    if data[:4] == b"RIFF":
        Path(out).write_bytes(data)
        return
    rate = re.search(r"rate=(\d+)", mime or "")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(PCM_CHANNELS)
        w.setsampwidth(PCM_WIDTH)
        w.setframerate(int(rate.group(1)) if rate else PCM_RATE)
        w.writeframes(data)
    Path(out).write_bytes(buf.getvalue())


def _mime(path) -> str:
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
        Path(path).suffix.lower(), "application/octet-stream")

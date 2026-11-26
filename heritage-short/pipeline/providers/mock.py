"""Mock providers: labelled placeholders so the whole pipeline runs offline in seconds.
Mock runs write only under build/mock/ and never touch real outputs or logs (ADR-016)."""
from __future__ import annotations

import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from .. import media


def estimate_speech_s(text: str, lang: str) -> float:
    if lang == "en":
        return len(text.split()) / 2.4 + 0.3
    return len(text.replace(" ", "")) / 9.0 + 0.3      # rough Ge'ez characters per second


class MockImage:
    name, model = "mock", "mock-image"

    def generate(self, *, prompt: str, seed: int, size, refs: list[Path], out: Path) -> dict:
        w, h = size
        rnd = random.Random(f"{prompt}|{seed}")
        top = tuple(rnd.randint(30, 190) for _ in range(3))
        bottom = tuple(rnd.randint(30, 190) for _ in range(3))
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        label = f"MOCK  seed {seed}  refs {len(refs)}\n" + textwrap.fill(prompt.splitlines()[0][:140], 26)
        draw.multiline_text((int(w * 0.06), int(h * 0.06)), label, fill=(255, 255, 255),
                            font=media.font(max(8, w // 22)))
        img.save(out, format="PNG")
        return {"params": {"refs": len(refs)}}


class MockSpeech:
    name, model = "mock", "mock-tts"

    def speak(self, *, text: str, lang: str, voice: dict, out: Path) -> dict:
        media.tone(out, estimate_speech_s(text, lang), freq=165 if lang == "en" else 190)
        return {"model": f"mock-tts ({voice.get('model', '?')})"}


class MockMusic:
    name, model = "mock", "mock-music"

    def compose(self, *, caption: str, seed: int, length_s: float, bpm=None, key=None,
                instrumental: bool = True, out: Path) -> dict:
        media.drone(out, length_s, seed=seed)
        return {}


class MockVideo:
    name, model = "mock", "mock-i2v"

    def animate(self, *, keyframe: Path, prompt: str, seed: int, frames: int, size, fps: int, out: Path) -> dict:
        media.kenburns(keyframe, out, tuple(size), frames / fps, fps, zoom="out", pan="right" if seed % 2 else "left")
        return {"gpu_s": 0.0}


class MockText:
    """Answers any structured-output request with the schema's own example, if it has one
    (`"examples": [...]` at the top level), or a minimal object that satisfies the schema."""
    name, model = "mock", "mock-text"

    def generate_json(self, *, prompt: str, schema: dict, system: str = "", images=(), temperature: float = 0.4):
        if schema.get("examples"):
            return schema["examples"][0], {"params": {"images": len(images)}}
        return _minimal(schema), {"params": {"images": len(images)}}


def _minimal(schema: dict):
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        props = schema.get("properties", {})
        return {k: _minimal(props[k]) for k in schema.get("required", []) if k in props}
    if kind == "array":
        return [_minimal(schema.get("items", {})) for _ in range(schema.get("minItems", 0))]
    if kind == "integer":
        return int(schema.get("minimum", 0))
    if kind == "number":
        return float(schema.get("minimum", 0))
    if kind == "boolean":
        return False
    return "mock"

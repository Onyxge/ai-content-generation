"""`film smoke`: one tiny call to each hosted provider, through the same runner as everything
else, so each call lands in runs.jsonl with its latency (brief, Phase 1 step 1). The day is
part of each unit's spec, so a smoke test runs once a day and re-running it the same day is
a cache hit, not another spend. Outputs go to outputs/smoke/, which is gitignored."""
from __future__ import annotations

import json
import os
from datetime import date

from .engine.runner import Stage, Unit

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
          "required": ["ok", "word"]}


class Smoke(Stage):
    name = "smoke"
    version = 1

    def units(self, ctx):
        s, day, out = ctx.cfg["smoke"], date.today().isoformat(), ctx.ws.outputs / "smoke"
        addis = []
        if ctx.ws.mock or os.environ.get("ADDIS_AI_API_KEY"):        # Addis AI is optional (E21)
            addis = [Unit(self.name, "speech_am", out / "speech_am.wav",
                          {"day": day, "text": s["addis_text"], "lang": "am",
                           "voice": {"model": "addis-voices-2", "voice": s["addis_voice"]}}, provider="speech")]
        return addis + [
            Unit(self.name, "text", out / "text.json", {"day": day, "prompt": s["text_prompt"]}, provider="text"),
            Unit(self.name, "speech", out / "speech.wav",
                 {"day": day, "text": s["speech_text"], "lang": "en",
                  "voice": {"model": s["speech_model"], "voice": s["speech_voice"], "style": s["speech_style"]}},
                 provider="speech"),
            Unit(self.name, "image", out / "image.png",
                 {"day": day, "prompt": s["image_prompt"], "seed": 7, "size": s["image_size"]}, provider="image"),
        ]

    def render(self, unit, ctx, inputs, out):
        p, spec = ctx.providers[unit.provider], unit.spec
        if unit.id == "text":
            data, info = p.generate_json(prompt=spec["prompt"], schema=SCHEMA, temperature=0.0)
            out.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
            return info
        if unit.id.startswith("speech"):
            return p.speak(text=spec["text"], lang=spec["lang"], voice=spec["voice"], out=out)
        return p.generate(prompt=spec["prompt"], seed=spec["seed"], size=tuple(spec["size"]), refs=[], out=out)

"""Stage: narration. One WAV per shot per language. Only the spoken words go to the
speech model; voice and style travel separately, because Gemini 3.8 TTS reads its text
verbatim (ADR-001, ADR-015). Units are keyed per language, so an English edit never
touches the Amharic audio."""
from __future__ import annotations

import sys

from .engine.runner import Stage, Unit


class Narration(Stage):
    name = "narration"
    version = 1

    def units(self, ctx):
        units = []
        for lang in ctx.sb["meta"]["languages"]:
            voice = ctx.sb["voices"][lang]
            for shot in ctx.sb["shots"]:
                text = (shot["narration"].get(lang) or "").strip()
                if not text:
                    continue
                units.append(Unit(self.name, f"{shot['id']}.{lang}",
                                  ctx.ws.outputs / "narration" / lang / f"{shot['id']}.wav",
                                  {"text": text, "lang": lang, "voice": voice}, provider="speech"))
        return units

    def render(self, unit, ctx, inputs, out):
        s = unit.spec
        return ctx.providers["speech"].speak(text=s["text"], lang=s["lang"], voice=s["voice"], out=out)


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["render", "--stage", Narration.name, *sys.argv[1:]]))

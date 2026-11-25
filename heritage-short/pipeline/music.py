"""Stage: music. Renders every seed of every cue as a candidate; Y listens under the
narration and pins one as `selected`, with the reason in `why` (E10). Length is fixed in
the storyboard, never derived from the film's runtime, so a narration edit can't
invalidate the score (ADR-010)."""
from __future__ import annotations

import sys

from .engine.runner import Stage, Unit

FIELDS = ("caption", "instrumental", "bpm", "key", "length_s")


class Music(Stage):
    name = "music"
    version = 1

    def units(self, ctx):
        units = []
        for cue in ctx.sb["music"]["cues"]:
            for seed in cue["seeds"]:
                spec = {k: cue.get(k) for k in FIELDS} | {"seed": seed}
                units.append(Unit(self.name, f"{cue['id']}.{seed}",
                                  ctx.ws.outputs / "music" / f"{cue['id']}.{seed}.wav", spec, provider="music"))
        return units

    def render(self, unit, ctx, inputs, out):
        s = unit.spec
        return ctx.providers["music"].compose(caption=s["caption"], seed=s["seed"], length_s=s["length_s"],
                                              bpm=s["bpm"], key=s["key"], instrumental=s["instrumental"], out=out)


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["render", "--stage", Music.name, *sys.argv[1:]]))

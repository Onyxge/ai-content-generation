"""Stage: references. Renders every seed of every reference sheet so Y can pick one;
the pick is pinned in storyboard.json as `selected` (ADR-009: explore, pick, pin)."""
from __future__ import annotations

import sys

from .engine.runner import Stage, Unit
from .prompts import image_prompt


class References(Stage):
    name = "references"
    version = 1

    def units(self, ctx):
        size = ctx.cfg["images"]["reference_size"]
        units = []
        for ref in ctx.sb["references"]:
            prompt = image_prompt(ctx.sb, ref["prompt"], ref.get("characters", []))
            for seed in ref["seeds"]:
                units.append(Unit(self.name, f"{ref['id']}.{seed}",
                                  ctx.ws.outputs / "references" / f"{ref['id']}.{seed}.png",
                                  {"prompt": prompt, "seed": seed, "size": size}, provider="image"))
        return units

    def render(self, unit, ctx, inputs, out):
        s = unit.spec
        return ctx.providers["image"].generate(prompt=s["prompt"], seed=s["seed"], size=tuple(s["size"]),
                                               refs=[], out=out)


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["render", "--stage", References.name, *sys.argv[1:]]))

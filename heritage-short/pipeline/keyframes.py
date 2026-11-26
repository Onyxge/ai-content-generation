"""Stage: keyframes. One still per shot, conditioned on the pinned reference options
(at most four, each downscaled under 512x512 by the real provider)."""
from __future__ import annotations

import sys

from .contract import shot_references
from .engine.runner import Stage, Unit
from .prompts import image_prompt


class Keyframes(Stage):
    name = "keyframes"
    version = 1

    def units(self, ctx):
        refs = {r["id"]: r for r in ctx.sb["references"]}
        size = ctx.cfg["images"]["keyframe_size"]
        units = []
        for shot in ctx.sb["shots"]:
            deps, blocked = [], ""
            for rid in shot_references(ctx.sb, shot):
                picked = refs.get(rid, {}).get("selected")
                if picked is None:
                    blocked = f"pick references/{rid}.selected first (options are in outputs/references/)"
                else:
                    deps.append(("references", f"{rid}.{picked}"))
            spec = {"prompt": image_prompt(ctx.sb, shot["image_prompt"], shot.get("characters", [])),
                    "seed": shot["keyframe_seed"], "size": size}
            if deps:                                 # only shots conditioned on a reference: s02's key, and its Wan clip, stay as they are
                spec["ref_view"] = ctx.cfg["images"].get("reference_view", "sheet")
            units.append(Unit(self.name, shot["id"], ctx.ws.outputs / "keyframes" / f"{shot['id']}.png",
                              spec, tuple(deps), provider="image", blocked=blocked))
        return units

    def render(self, unit, ctx, inputs, out):
        s = unit.spec
        refs = [view_of(p, s.get("ref_view", "sheet"), out.parent / f".ref-{unit.id}-{i}.png")
                for i, p in enumerate(inputs.values())]
        try:
            return ctx.providers["image"].generate(prompt=s["prompt"], seed=s["seed"], size=tuple(s["size"]),
                                                   refs=refs, out=out)
        finally:
            for r in refs:
                if r.name.startswith(".ref-"):
                    r.unlink(missing_ok=True)


def view_of(sheet, view: str, tmp):
    """The part of a reference sheet a keyframe is conditioned on. Given the whole three-view
    character sheet, FLUX copied its layout and painted the same man two or three times in one
    frame (s01, s06, s10 on 2026-11-26; FAILURES.md F10). "front" conditions on the sheet's
    left third, its front view, so the model sees one person."""
    if view == "sheet":
        return sheet
    from PIL import Image

    img = Image.open(sheet).convert("RGB")
    img.crop((0, 0, img.width // 3, img.height)).save(tmp)
    return tmp


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["render", "--stage", Keyframes.name, *sys.argv[1:]]))

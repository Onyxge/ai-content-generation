"""Stage: shots. Every shot gets Ken Burns clips rendered locally in both orientations,
so a complete film always exists (ADR-005). Shots marked `i2v` also get a Wan clip from
the GPU runner; assembly uses it once it's in the cache and falls back otherwise. Clip
lengths come from the storyboard, never from the measured narration (ADR-010)."""
from __future__ import annotations

import sys

from . import media
from .engine.runner import Stage, Unit


class Shots(Stage):
    name = "shots"
    version = 1

    def units(self, ctx):
        video, delivery = ctx.cfg["video"], ctx.cfg["delivery"]
        units = []
        for shot in ctx.sb["shots"]:
            deps = (("keyframes", shot["id"]),)
            motion = shot["motion"]
            kb = motion.get("kenburns", {})
            still = motion["mode"] == "still" or motion.get("fallback") == "still"
            zoom = "none" if still else kb.get("zoom", "in")
            pan = "none" if still else kb.get("pan", "none")
            for orient in ("vertical", "horizontal"):
                spec = {"kind": "kenburns", "orient": orient, "size": delivery[orient], "fps": video["fps"],
                        "duration_s": shot["duration_s"] + video["kenburns_headroom_s"], "zoom": zoom, "pan": pan}
                units.append(Unit(self.name, f"{shot['id']}.kb.{orient[0]}",
                                  ctx.ws.outputs / "shots" / f"{shot['id']}.kb.{orient[0]}.mp4", spec, deps))
            if motion["mode"] == "i2v":
                spec = {"kind": "i2v", "prompt": motion["prompt"], "seed": motion.get("seed", 0),
                        "size": video["i2v_size"], "frames": video["i2v_frames"], "fps": video["fps"]}
                units.append(Unit(self.name, f"{shot['id']}.i2v",
                                  ctx.ws.outputs / "shots" / f"{shot['id']}.i2v.mp4", spec, deps, provider="video"))
        return units

    def render(self, unit, ctx, inputs, out):
        keyframe = next(iter(inputs.values()))
        s = unit.spec
        if s["kind"] == "kenburns":
            media.kenburns(keyframe, out, tuple(s["size"]), s["duration_s"], s["fps"], zoom=s["zoom"], pan=s["pan"])
            return None
        return ctx.providers["video"].animate(keyframe=keyframe, prompt=s["prompt"], seed=s["seed"],
                                              frames=s["frames"], size=s["size"], fps=s["fps"], out=out)


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["render", "--stage", Shots.name, *sys.argv[1:]]))

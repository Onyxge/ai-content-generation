"""Stage: assemble. Always reruns, because it's cheap and deterministic (ADR-004).

For each language it builds a timeline from the measured narration (picture is fitted to
the voice, ADR-010), picks each shot's clip (a Wan clip if one is cached, otherwise Ken
Burns), ducks the score under the narration, burns in English subtitles, normalises the
loudness, adds the AI end card and exports both orientations. `radio_cut` makes the
user-test prototype: narration over a temp drone on black, with subtitles."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageDraw

from . import media
from .engine.runner import Ctx, Outcome
from .subtitles import write_srt

ORIENTS = {"vertical": "9x16", "horizontal": "16x9"}
# libass scales these to the frame (an SRT's script size is 384x288). The vertical margins keep
# subtitles clear of the buttons phone apps draw along the bottom and right of the frame.
STYLE = {
    "vertical": "FontName=DejaVu Sans,FontSize=9,Outline=1.2,Shadow=0,MarginV=56,MarginL=40,MarginR=40,Alignment=2",
    "horizontal": "FontName=DejaVu Sans,FontSize=15,Outline=1.2,Shadow=0,MarginV=18,MarginL=30,MarginR=30,Alignment=2",
}


class AssemblyError(RuntimeError):
    pass


def ready(outcomes: list[Outcome]) -> dict[tuple[str, str], Path]:
    """Artifacts that are current for this storyboard."""
    return {o.unit.ref: o.unit.out for o in outcomes if o.state in ("hit", "built")}


def build_timeline(ctx: Ctx, lang: str, have: dict) -> dict:
    a, fps = ctx.cfg["audio"], ctx.cfg["video"]["fps"]
    t, shots = 0.0, []
    for s in ctx.sb["shots"]:
        entry = {"id": s["id"], "start": round(t, 3)}
        length = s["duration_s"]
        if (s["narration"].get(lang) or "").strip():
            wav = have.get(("narration", f"{s['id']}.{lang}"))
            if wav is None:
                raise AssemblyError(f"narration {s['id']}.{lang} isn't rendered for the current storyboard; "
                                    "run `film render` first")
            spoken = media.wav_duration(wav)
            length = max(length, a["lead_in_s"] + spoken + a["tail_s"])
            entry["narration"] = {"file": ctx.ws.rel(wav), "start": round(t + a["lead_in_s"], 3),
                                  "duration": round(spoken, 3)}
        length = round(length * fps) / fps            # whole frames, so picture and sound never drift
        entry["length"] = length
        shots.append(entry)
        t += length
    end = ctx.sb["end_card"]["duration_s"]
    return {"language": lang, "fps": fps, "shots": shots, "end_card": {"start": round(t, 3), "length": end},
            "total_s": round(t + end, 3)}


def _pick_clip(shot: dict, orient: str, have: dict) -> tuple[Path, str]:
    clip = have.get(("shots", f"{shot['id']}.i2v"))
    if clip is not None:
        return clip, "i2v"
    clip = have.get(("shots", f"{shot['id']}.kb.{orient[0]}"))
    if clip is None:
        raise AssemblyError(f"no picture for {shot['id']} ({orient}); run `film render` first")
    return clip, "kenburns"


def _shot_chain(i: int, kind: str, orient: str, w: int, h: int, length: float, fps: int) -> str:
    tail = (f"tpad=stop_mode=clone:stop_duration={length:.3f},trim=duration={length:.3f},"
            f"setpts=PTS-STARTPTS,fps={fps},format=yuv420p,setsar=1[v{i}]")
    if kind == "i2v" and orient == "horizontal":      # vertical master into 16:9: blurred fill (ADR-011)
        return (f"[{i}:v]split=2[b{i}][f{i}];"
                f"[b{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2[bg{i}];"
                f"[f{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,{tail}")
    return f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},{tail}"


def _music(ctx: Ctx, have: dict, seconds: float, wd: Path) -> tuple[Path, str]:
    cue = ctx.sb["music"]["cues"][0]
    seed = cue.get("selected", cue["seeds"][0])
    path = have.get(("music", f"{cue['id']}.{seed}"))
    if path is not None:
        return path, f"{cue['id']}.{seed}"
    temp = wd / "temp_drone.wav"
    media.drone(temp, seconds + 1.0)
    return temp, "temp drone (no score rendered yet)"


def _audio(ctx: Ctx, tl: dict, music: Path, first: int) -> tuple[list[str], list[str]]:
    """Inputs and filters for the soundtrack: narration placed on the timeline, the score
    ducked under it with sidechain compression, then loudness-normalised. Ends in [aout]."""
    a, total = ctx.cfg["audio"], tl["total_s"]
    args, graph, voices, idx = [], [], [], first
    for entry in tl["shots"]:
        spoken = entry.get("narration")
        if not spoken:
            continue
        args += ["-i", str(ctx.ws.root / spoken["file"])]
        delay = int(round(spoken["start"] * 1000))
        graph.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=delays={delay}:all=1[n{idx}]")
        voices.append(f"[n{idx}]")
        idx += 1
    if voices:
        graph.append(f"{''.join(voices)}amix=inputs={len(voices)}:normalize=0:dropout_transition=0,"
                     f"apad=whole_dur={total:.3f}[voice]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{total:.3f}[voice]")
    args += ["-i", str(music)]
    graph += [
        "[voice]asplit=2[vmix][vsc]",
        f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
        f"apad=whole_dur={total:.3f},volume={a['music_gain']},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={max(0.0, total - 3):.3f}:d=3[music]",
        f"[music][vsc]sidechaincompress=threshold={a['duck_threshold']}:ratio={a['duck_ratio']}:"
        f"attack={a['duck_attack_ms']}:release={a['duck_release_ms']}[ducked]",
        f"[vmix][ducked]amix=inputs=2:normalize=0:duration=longest,atrim=0:{total:.3f},"
        f"loudnorm=I={a['target_lufs']}:TP={a['true_peak_db']}:LRA=11,aresample=48000[aout]",
    ]
    return args, graph


def _end_card(lines: list[str], size, path: Path) -> None:
    w, h = size
    img = Image.new("RGB", (w, h), (14, 14, 16))
    draw = ImageDraw.Draw(img)
    base = min(w, h)
    title, body = media.font(max(8, int(base * 0.08)), bold=True), media.font(max(6, int(base * 0.035)))
    width = max(12, int(w / (getattr(body, "size", 10) * 0.55)))
    blocks = [(lines[0], title, (245, 245, 245))]
    blocks += [(textwrap.fill(line, width=width), body, (190, 190, 190)) for line in lines[1:]]
    gap = int(base * 0.03)
    boxes = [draw.multiline_textbbox((0, 0), text, font=f, align="center") for text, f, _ in blocks]
    y = (h - sum(b[3] - b[1] for b in boxes) - gap * (len(blocks) - 1)) // 2
    for (text, f, colour), box in zip(blocks, boxes):
        draw.multiline_text(((w - (box[2] - box[0])) // 2 - box[0], y - box[1]), text, font=f, fill=colour,
                            align="center")
        y += box[3] - box[1] + gap
    img.save(path)


@contextmanager
def _workdir():
    """A scratch folder holding the SRT and the bundled fonts, so FFmpeg's subtitles filter
    gets plain relative paths on every OS and renders the same font everywhere."""
    with tempfile.TemporaryDirectory(prefix="film-") as d:
        wd = Path(d)
        shutil.copytree(media.FONTS, wd / "fonts")
        yield wd


def _encode_args(ctx: Ctx, total: float, out: Path) -> list[str]:
    d, fps = ctx.cfg["delivery"], ctx.cfg["video"]["fps"]
    return ["-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", d["preset"], "-crf", str(d["crf"]),
            "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)]


def _save_text_outputs(ctx: Ctx, tl: dict, srt: Path, lang: str, orient: str) -> None:
    (ctx.ws.outputs / "timeline").mkdir(parents=True, exist_ok=True)
    (ctx.ws.outputs / "timeline" / f"{lang}.json").write_text(json.dumps(tl, indent=2, ensure_ascii=False) + "\n",
                                                              encoding="utf-8")
    (ctx.ws.outputs / "subtitles").mkdir(parents=True, exist_ok=True)
    shutil.copy(srt, ctx.ws.outputs / "subtitles" / f"{lang}_{ORIENTS[orient]}.en.srt")


def _measure(ctx: Ctx, unit: str, out: Path, tl: dict, extra: dict) -> dict:
    record = {"stage": "assemble", "unit": unit, "output": ctx.ws.rel(out),
              "duration_s": round(media.probe_duration(out), 3), "planned_s": tl["total_s"],
              **media.loudness(out), **extra}
    ctx.log.stage(**record)
    return record


def export(ctx: Ctx, lang: str, orient: str, have: dict) -> dict:
    w, h = ctx.cfg["delivery"][orient]
    fps, sub = ctx.cfg["video"]["fps"], ctx.cfg["subtitles"]
    tl = build_timeline(ctx, lang, have)
    total = tl["total_s"]
    out = ctx.ws.outputs / "final" / f"film_{lang}_{ORIENTS[orient]}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    with _workdir() as wd:
        cards = write_srt(ctx.sb, tl, wd / "subs.srt", sub["max_chars"][orient], sub["max_lines"])
        args, graph, kinds = [], [], {}
        shots = ctx.sb["shots"]
        for i, (shot, entry) in enumerate(zip(shots, tl["shots"])):
            clip, kind = _pick_clip(shot, orient, have)
            kinds[shot["id"]] = kind
            args += ["-i", str(clip)]
            graph.append(_shot_chain(i, kind, orient, w, h, entry["length"], fps))
        n, end = len(shots), tl["end_card"]["length"]
        _end_card(ctx.sb["end_card"]["lines"], (w, h), wd / "endcard.png")
        args += ["-loop", "1", "-framerate", str(fps), "-t", f"{end:.3f}", "-i", str(wd / "endcard.png")]
        graph.append(f"[{n}:v]scale={w}:{h},fps={fps},format=yuv420p,setsar=1,trim=duration={end:.3f},"
                     f"setpts=PTS-STARTPTS[v{n}]")
        graph.append("".join(f"[v{i}]" for i in range(n + 1)) + f"concat=n={n + 1}:v=1:a=0[vcat]")
        graph.append(f"[vcat]subtitles=filename=subs.srt:fontsdir=fonts:force_style='{STYLE[orient]}'[vout]"
                     if cards else "[vcat]null[vout]")
        music, music_label = _music(ctx, have, total, wd)
        audio_args, audio_graph = _audio(ctx, tl, music, first=n + 1)
        media.ffmpeg([*args, *audio_args, "-filter_complex", ";".join(graph + audio_graph),
                      *_encode_args(ctx, total, out)], cwd=wd)
        _save_text_outputs(ctx, tl, wd / "subs.srt", lang, orient)
    return _measure(ctx, f"{lang}.{orient}", out, tl,
                    {"pictures": dict(Counter(kinds.values())), "music": music_label, "subtitle_cards": cards})


def radio_cut(ctx: Ctx, lang: str, have: dict) -> dict:
    w, h = ctx.cfg["delivery"]["vertical"]
    fps, sub = ctx.cfg["video"]["fps"], ctx.cfg["subtitles"]
    tl = build_timeline(ctx, lang, have)
    total = tl["total_s"]
    out = ctx.ws.outputs / "radio" / f"radio_{lang}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    with _workdir() as wd:
        cards = write_srt(ctx.sb, tl, wd / "subs.srt", sub["max_chars"]["vertical"], sub["max_lines"])
        subs = f",subtitles=filename=subs.srt:fontsdir=fonts:force_style='{STYLE['vertical']}'" if cards else ""
        drone = wd / "temp_drone.wav"
        media.drone(drone, total + 1.0)
        audio_args, audio_graph = _audio(ctx, tl, drone, first=0)
        video = f"color=c=black:s={w}x{h}:r={fps}:d={total:.3f},format=yuv420p{subs}[vout]"
        media.ffmpeg([*audio_args, "-filter_complex", ";".join([video, *audio_graph]),
                      *_encode_args(ctx, total, out)], cwd=wd)
    return _measure(ctx, f"radio.{lang}", out, tl, {"music": "temp drone", "subtitle_cards": cards})


def assemble(ctx: Ctx, outcomes: list[Outcome], langs=None, orients=None) -> list[dict]:
    have = ready(outcomes)
    return [export(ctx, lang, orient, have)
            for lang in (langs or ctx.sb["meta"]["languages"]) for orient in (orients or list(ORIENTS))]


def radio(ctx: Ctx, outcomes: list[Outcome], langs=None) -> list[dict]:
    have = ready(outcomes)
    return [radio_cut(ctx, lang, have) for lang in (langs or ctx.sb["meta"]["languages"])]


if __name__ == "__main__":
    from .cli import main
    raise SystemExit(main(["assemble", *sys.argv[1:]]))

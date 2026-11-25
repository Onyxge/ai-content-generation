"""FFmpeg and audio helpers. Nothing in this module calls a model."""
from __future__ import annotations

import re
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import ImageFont

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "assets" / "fonts"
FONT_REGULAR = FONTS / "DejaVuSans.ttf"
FONT_BOLD = FONTS / "DejaVuSans-Bold.ttf"


def _exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is not on PATH. Install FFmpeg (see README) and run again.")
    return path


def ffmpeg(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([_exe("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args],
                          cwd=cwd, check=True, capture_output=True, text=True)


def probe_duration(path: Path) -> float:
    out = subprocess.run([_exe("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def loudness(path: Path) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP) of a finished file, via FFmpeg's ebur128."""
    p = subprocess.run([_exe("ffmpeg"), "-hide_banner", "-nostdin", "-nostats", "-i", str(path),
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    integrated = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    return {"integrated_lufs": float(integrated[-1]) if integrated else None,
            "true_peak_db": float(peak[-1]) if peak else None}


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)
    except OSError:
        return ImageFont.load_default()


def kenburns(image: Path, out: Path, size, seconds: float, fps: int,
             zoom: str = "in", pan: str = "none", strength: float = 0.12) -> None:
    """A slow pan and zoom over a still. The image is centre-cropped to the target aspect and
    upscaled 2x first, which keeps zoompan's per-frame rounding from jittering."""
    w, h = size
    n = max(2, round(seconds * fps))
    z = {"in": f"1+{strength}*on/{n}", "out": f"{1 + strength}-{strength}*on/{n}"}.get(zoom, "1")
    x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*on/{n}"}.get(pan, "iw/2-(iw/zoom/2)")
    y = "ih/2-(ih/zoom/2)"
    vf = (f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})',scale={2 * w}:{2 * h},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={fps},format=yuv420p,setsar=1")
    ffmpeg(["-i", str(image), "-vf", vf, "-frames:v", str(n), "-r", str(fps), "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-f", "mp4", str(out)])


def tone(out: Path, seconds: float, freq: float, sample_rate: int = 24000, tremolo_hz: float = 4.0) -> None:
    """A speech-like placeholder: a tone pulsing at roughly syllable rate."""
    d = max(0.2, seconds)
    ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate={sample_rate}:duration={d:.3f}",
            "-af", f"tremolo=f={tremolo_hz}:d=0.9,volume=0.6,afade=t=in:d=0.05,"
                   f"afade=t=out:st={max(0.0, d - 0.12):.3f}:d=0.12",
            "-ac", "1", "-c:a", "pcm_s16le", "-f", "wav", str(out)])


def drone(out: Path, seconds: float, seed: int = 0, sample_rate: int = 48000) -> None:
    """A synthetic temp track: root, fifth and octave with a slow tremolo. Not a model call."""
    root = 98.0 * 2 ** ((seed % 7) / 12)
    inputs: list[str] = []
    for f in (root, root * 1.5, root * 2.0):
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f:.2f}:sample_rate={sample_rate}:duration={seconds:.3f}"]
    ffmpeg([*inputs, "-filter_complex",
            f"[0][1][2]amix=inputs=3:normalize=0,volume=0.15,tremolo=f=0.15:d=0.5,afade=t=in:d=2,"
            f"afade=t=out:st={max(0.0, seconds - 3):.3f}:d=3,aformat=channel_layouts=stereo",
            "-c:a", "pcm_s16le", "-f", "wav", str(out)])

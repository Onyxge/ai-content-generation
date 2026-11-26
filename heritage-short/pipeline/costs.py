"""`film costs` (U9): the measured tables in COSTS.md, regenerated from runs.jsonl and stages.jsonl.

Everything between the two markers in COSTS.md is rewritten on each run; the prose around it
is kept. Prices are list-price equivalents: free-tier work, priced as if paid, so the film's
real cost is visible. Every price comes from config/pricing.toml, with its source and the date
it was checked. A provider without a checked price is shown as "no checked price", never guessed."""
from __future__ import annotations

import statistics
import tomllib
from collections import defaultdict
from pathlib import Path

from .engine.logs import read_jsonl

BEGIN = "<!-- film costs: generated from runs.jsonl and stages.jsonl; edits between these markers are overwritten -->"
END = "<!-- end of generated tables -->"


def _p95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    return statistics.quantiles(values, n=20)[-1]


def tables(runs: list[dict], stages: list[dict], pricing: dict) -> str:
    rows = defaultdict(lambda: {"attempts": 0, "ok": 0, "failed": defaultdict(int), "lat": [], "gpu": 0.0, "units": set()})
    for r in runs:
        key = (r.get("stage"), r.get("provider"), r.get("model"))
        row = rows[key]
        row["attempts"] += 1
        if r.get("status") == "ok":
            row["ok"] += 1
            row["units"].add(r.get("unit"))
            if r.get("latency_ms") is not None:
                row["lat"].append(r["latency_ms"] / 1000)
        else:
            row["failed"][r.get("status", "error")] += 1
        if r.get("gpu_s"):
            row["gpu"] += float(r["gpu_s"])

    out = ["### Every model call, by stage and model", "",
           "| Stage | Provider | Model | Attempts | OK | Failed (by kind) | Median s | p95 s | GPU min | List-price equivalent |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    total_usd = 0.0
    for (stage, provider, model), row in sorted(rows.items(), key=lambda kv: [str(x) for x in kv[0]]):
        failed = ", ".join(f"{k} {v}" for k, v in sorted(row["failed"].items())) or "—"
        med = f"{statistics.median(row['lat']):.1f}" if row["lat"] else "—"
        p95 = f"{_p95(row['lat']):.1f}" if row["lat"] else "—"
        gpu = f"{row['gpu'] / 60:.1f}" if row["gpu"] else "—"
        price = _price(pricing, provider, model, row)
        if isinstance(price, float):
            total_usd += price
            price = f"${price:.3f}"
        out.append(f"| {stage} | {provider} | {model} | {row['attempts']} | {row['ok']} | {failed} | {med} | {p95} | {gpu} | {price} |")
    gpu_total = sum(r["gpu"] for r in rows.values())
    out += ["", f"Totals: {sum(r['attempts'] for r in rows.values())} attempts, "
                f"{sum(r['ok'] for r in rows.values())} succeeded; GPU {gpu_total / 60:.1f} min; "
                f"priced items ${total_usd:.2f} at list price (unpriced rows excluded).", ""]

    finals = {}
    for s in stages:
        if s.get("stage") == "assemble" and "integrated_lufs" in s:
            finals[s["unit"]] = s
    if finals:
        out += ["### Exports, as measured at the last assembly", "",
                "| Export | Duration s | Integrated LUFS | True peak dB | Pictures | Music |", "|---|---|---|---|---|---|"]
        for unit, s in sorted(finals.items()):
            pics = s.get("pictures", "—")
            pics = ", ".join(f"{k} {v}" for k, v in pics.items()) if isinstance(pics, dict) else pics
            out.append(f"| {unit} | {s.get('duration_s')} | {s.get('integrated_lufs')} | {s.get('true_peak_db')} | {pics} | {s.get('music', '—')} |")
        out.append("")
    return "\n".join(out)


def _price(pricing: dict, provider, model, row):
    """List-price equivalent for a row, or a note saying why there isn't one."""
    p = pricing.get("models", {}).get(str(model)) or pricing.get("providers", {}).get(str(provider).split(" ")[0])
    if not p:
        return "no checked price"
    if "usd_per_call" in p:
        return row["ok"] * p["usd_per_call"]
    if "usd_per_gpu_hour" in p:
        return row["gpu"] / 3600 * p["usd_per_gpu_hour"]
    return "no checked price"


def write(root: Path) -> str:
    base = Path(root)
    pricing_path = base / "config" / "pricing.toml"
    pricing = tomllib.loads(pricing_path.read_text(encoding="utf-8")) if pricing_path.exists() else {}
    body = tables(read_jsonl(base / "runs.jsonl"), read_jsonl(base / "stages.jsonl"), pricing)
    costs = base / "COSTS.md"
    text = costs.read_text(encoding="utf-8") if costs.exists() else "# COSTS\n"
    block = f"{BEGIN}\n\n{body}\n{END}"
    if BEGIN in text and END in text:
        text = text[: text.index(BEGIN)] + block + text[text.index(END) + len(END):]
    else:
        text = text.rstrip("\n") + "\n\n## Measured, from the logs (`film costs`)\n\n" + block + "\n"
    costs.write_text(text, encoding="utf-8")
    return body

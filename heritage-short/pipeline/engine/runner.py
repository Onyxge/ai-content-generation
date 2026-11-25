"""The runner. Evaluates every unit against the cache, builds the misses in dependency order,
retries transient failures and logs every model call (ADR-004, ADR-007, ADR-008).

Dry runs (`film plan`) use the same code path without building anything: a unit whose
upstream would change is reported as `upstream`, so the plan shows exactly what an edit
will regenerate before any quota is spent."""
from __future__ import annotations

import os
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .cache import is_fresh, unit_key, write_sidecar
from .logs import RunLog
from .retry import DailyQuotaError, ProviderError, ProviderUnavailable, call_with_retry
from .workspace import Workspace, sha256_file, sha256_text

READY = ("hit", "built")
TEXT_FIELDS = ("prompt", "text", "caption")


@dataclass(frozen=True)
class Unit:
    stage: str
    id: str
    out: Path
    spec: dict                                   # everything that determines the output
    deps: tuple[tuple[str, str], ...] = ()       # (stage, unit id) pairs this unit reads
    provider: str | None = None                  # key in ctx.providers; None = local deterministic render
    blocked: str = ""                            # why the storyboard can't produce this unit yet

    @property
    def ref(self) -> tuple[str, str]:
        return (self.stage, self.id)


@dataclass
class Ctx:
    ws: Workspace
    sb: dict
    cfg: dict
    providers: dict
    log: RunLog


class Stage:
    name = ""
    version = 1

    def units(self, ctx: Ctx) -> list[Unit]:
        raise NotImplementedError

    def render(self, unit: Unit, ctx: Ctx, inputs: dict[str, Path], out: Path) -> dict | None:
        """Write the artifact to `out` (a temporary path) and return extra log fields."""
        raise NotImplementedError


@dataclass
class Outcome:
    unit: Unit
    state: str            # hit | miss | upstream | blocked | built | failed | deferred | pending
    key: str | None = None
    note: str = ""

    def as_dict(self) -> dict:
        return {"stage": self.unit.stage, "unit": self.unit.id, "state": self.state,
                "provider": self.unit.provider or "local", "note": self.note}


def execute(ctx: Ctx, stages: list[Stage], *, dry: bool = False, only: set[str] | None = None) -> list[Outcome]:
    results: dict[tuple[str, str], Outcome] = {}
    exhausted: set[str] = set()
    ordered: list[Outcome] = []
    for stage in stages:
        started = time.perf_counter()
        counts: Counter = Counter()
        build_here = not dry and (only is None or stage.name in only)
        for unit in stage.units(ctx):
            outcome = _evaluate(stage, unit, ctx, results)
            if outcome.state == "miss" and build_here:
                outcome = _build(stage, unit, ctx, outcome.key, results, exhausted)
            results[unit.ref] = outcome
            ordered.append(outcome)
            counts[outcome.state] += 1
        if build_here:
            ctx.log.stage(stage=stage.name, counts=dict(counts), wall_s=round(time.perf_counter() - started, 2))
    return ordered


def _provider(ctx: Ctx, unit: Unit):
    return ctx.providers.get(unit.provider) if unit.provider else None


def _evaluate(stage: Stage, unit: Unit, ctx: Ctx, results: dict) -> Outcome:
    if unit.blocked:
        return Outcome(unit, "blocked", note=unit.blocked)
    upstream: dict[str, str] = {}
    for dep in unit.deps:
        name = f"{dep[0]}:{dep[1]}"
        d = results.get(dep)
        if d is None:
            return Outcome(unit, "blocked", note=f"unknown dependency {name}")
        if d.state in ("miss", "upstream"):
            return Outcome(unit, "upstream", note=f"{name} changes first")
        if d.state not in READY:
            return Outcome(unit, "blocked", note=f"{name} is {d.state}")
        upstream[name] = sha256_file(d.unit.out)
    provider = _provider(ctx, unit)
    material = {"stage": stage.name, "stage_version": stage.version,
                "provider": getattr(provider, "name", "local"), "model": getattr(provider, "model", "ffmpeg"),
                "spec": unit.spec, "upstream": upstream}
    key = unit_key(material)
    return Outcome(unit, "hit" if is_fresh(unit.out, key) else "miss", key)


def _build(stage: Stage, unit: Unit, ctx: Ctx, key: str, results: dict, exhausted: set[str]) -> Outcome:
    provider = _provider(ctx, unit)
    if unit.provider in exhausted:
        return Outcome(unit, "deferred", key, f"{unit.provider}: daily quota used up earlier in this run")
    inputs = {f"{s}:{u}": results[(s, u)].unit.out for s, u in unit.deps}
    unit.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = unit.out.with_name(f".tmp-{unit.out.name}")
    text = next((unit.spec[f] for f in TEXT_FIELDS if f in unit.spec), None)

    def on_attempt(n, status, ms, err, info):
        if provider is None or status == "unavailable":
            return                     # local renders and calls that never happened are not model calls
        info = info or {}
        ok = status == "ok"
        ctx.log.model_call(
            stage=stage.name, unit=unit.id, attempt=n,
            provider=provider.name, model=info.get("model", provider.model),
            params={k: v for k, v in unit.spec.items() if k not in TEXT_FIELDS and k != "seed"} | info.get("params", {}),
            seed=unit.spec.get("seed"),
            prompt_sha=sha256_text(text)[:12] if text else None,
            cache_key=key[:12], status=status, latency_ms=ms,
            gpu_s=info.get("gpu_s"), cost_usd_list=info.get("cost_usd_list"),
            output=ctx.ws.rel(unit.out) if ok else None,
            output_sha=sha256_file(tmp)[:12] if ok else None,
            error=str(err)[:300] if err else None,
        )

    try:
        info = call_with_retry(lambda: stage.render(unit, ctx, inputs, tmp) or {}, on_attempt)
    except (ProviderError, subprocess.CalledProcessError) as e:
        tmp.unlink(missing_ok=True)    # a half-written file must never look cached
        if isinstance(e, DailyQuotaError):
            exhausted.add(unit.provider)
            return Outcome(unit, "deferred", key, str(e))
        if isinstance(e, ProviderUnavailable):
            return Outcome(unit, "pending" if e.pending else "failed", key, str(e))
        if isinstance(e, subprocess.CalledProcessError):
            return Outcome(unit, "failed", key, f"FFmpeg failed: {(e.stderr or str(e))[-300:]}")
        return Outcome(unit, "failed", key, f"{e.status}: {e}")
    os.replace(tmp, unit.out)          # only a complete file ever gets the real name
    write_sidecar(unit.out, key, {"stage": stage.name, "unit": unit.id, "run_id": ctx.ws.run_id,
                                  "provider": getattr(provider, "name", "local"),
                                  "model": info.get("model", getattr(provider, "model", "ffmpeg")),
                                  "seed": unit.spec.get("seed")})
    return Outcome(unit, "built", key)

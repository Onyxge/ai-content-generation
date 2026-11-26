"""Proposals and the decision log (ADR-018, ADR-019).

Agents never write storyboard.json. They hand `propose()` a JSON Patch over the id-keyed
view (see patches.py), a rationale and their evidence. Before anyone sees it, a proposal
must pass four checks:

1. ownership: every changed path is one the agent owns or a pin (config/agents.toml),
   and nothing only Y may change is touched;
2. the schema, 3. the lint and its consent gate, on the patched storyboard;
4. a price: what `film plan` would generate if it landed.

Then the autonomy of its kind decides: `propose` waits for Y, `veto` applies now and waits
for Y to confirm or revert, `auto` applies. Every step appends one line to decisions.jsonl,
and each proposal is kept as proposals/P-nnnn.json, refused ones included, because the
refusals are the evidence that the guardrails work."""
from __future__ import annotations

import json
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import contract
from ..engine.logs import append_jsonl, read_jsonl
from ..engine.workspace import canonical, sha256_text, utc_now
from . import patches
from .patches import MISSING, ORDER, PatchError

HUMAN = "Y"
STRICTNESS = {"propose": 0, "veto": 1, "auto": 2}


class DecisionError(Exception):
    """A request that can't be carried out, such as approving a proposal that isn't pending."""


# ---------- policy ----------

@dataclass
class Policy:
    agents: dict[str, dict]
    y_only: list[str]
    pins: list[str]
    kinds: dict[str, str]
    autonomy: dict[str, str]
    budgets: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> "Policy":
        with open(Path(root) / "config" / "agents.toml", "rb") as f:
            raw = tomllib.load(f)
        return cls(agents=raw.get("agents", {}), y_only=raw.get("y_only", []), pins=raw.get("pins", []),
                   kinds=raw.get("kinds", {}), autonomy=raw.get("autonomy", {}), budgets=raw.get("budgets", {}))

    def owner_of(self, path: str) -> str | None:
        if any(patches.matches(p, path) for p in self.y_only):
            return HUMAN
        for name, spec in self.agents.items():
            if any(patches.matches(p, path) for p in spec.get("owns", [])):
                return name
            if _structural(path) in spec.get("creates", []):
                return name
        return None

    def kind_of(self, actor: str, path: str) -> str:
        return next((k for p, k in self.kinds.items() if patches.matches(p, path)), actor)

    def autonomy_of(self, kinds: list[str]) -> str:
        levels = [self.autonomy.get(k, "propose") for k in kinds] or ["propose"]
        return min(levels, key=lambda level: STRICTNESS.get(level, 0))


def _structural(path: str) -> str | None:
    """For an item or ordering path (`/shots/s13`, `/shots/@order`) return its collection."""
    parts = patches.split(path)
    parent = patches.join(parts[:-1])
    return parent if parent in patches.COLLECTIONS else None


def ownership_errors(policy: Policy, actor: str, changes) -> list[str]:
    if actor == HUMAN:
        return []
    spec = policy.agents.get(actor)
    if spec is None:
        return [f"'{actor}' is not an agent in config/agents.toml"]
    errors = []
    for path, _, _ in changes:
        if any(patches.matches(p, path) for p in policy.y_only):
            errors.append(f"{path}: only Y may change this")
            continue
        collection = _structural(path)
        if collection is not None:
            if collection not in spec.get("creates", []):
                errors.append(f"{path}: {actor} may not add, remove or reorder items in {collection}")
            continue
        if any(patches.matches(p, path) for p in spec.get("owns", []) + policy.pins):
            continue
        owner = policy.owner_of(path)
        errors.append(f"{path}: not {actor}'s to change" + (f" (owned by {owner})" if owner else ""))
    return errors


# ---------- the studio's decision state ----------

def storyboard_sha(sb: dict) -> str:
    return sha256_text(canonical(sb))[:12]


def _encode(value):
    return {"missing": True} if value is MISSING else {"value": value}


def _decode(cell: dict):
    return MISSING if cell.get("missing") else cell["value"]


class Decisions:
    """Proposals and decisions for one workspace: the repo root, or build/mock/ for mock runs."""

    def __init__(self, root: Path, storyboard: Path, mock: bool = False):
        self.root = Path(root).resolve()
        self.storyboard = Path(storyboard).resolve()
        self.base = self.root / "build" / "mock" if mock else self.root
        self.mock = mock
        self.policy = Policy.load(self.root)

    # paths
    @property
    def log_path(self) -> Path:
        return self.base / "decisions.jsonl"

    @property
    def proposals_dir(self) -> Path:
        return self.base / "proposals"

    def _proposal_path(self, pid: str) -> Path:
        return self.proposals_dir / f"{pid}.json"

    # storyboard io
    def read_storyboard(self) -> dict:
        return contract.load(self.storyboard)

    def _write_storyboard(self, sb: dict) -> None:
        tmp = self.storyboard.with_name(f".tmp-{self.storyboard.name}")
        tmp.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.storyboard)

    def validate(self, sb: dict) -> contract.Report:
        errors = contract.schema_errors(sb)
        if errors:
            return contract.Report(errors=errors)
        ethics = self.root / "ETHICS.md"
        return contract.lint(sb, ethics.read_text(encoding="utf-8") if ethics.exists() else "")

    def price(self, sb: dict) -> dict:
        """What `film plan` would generate if this storyboard were current: a dry run, no calls."""
        from .. import providers
        from ..config import load_config
        from ..engine.logs import RunLog
        from ..engine.runner import Ctx, execute
        from ..engine.workspace import Workspace
        from ..registry import stages

        cfg = load_config(self.root)
        ws = Workspace.create(self.root, mock=self.mock)
        ctx = Ctx(ws=ws, sb=sb, cfg=cfg, providers=providers.load(cfg, self.mock), log=RunLog(ws))
        todo = [o for o in execute(ctx, stages(), dry=True) if o.state in ("miss", "upstream")]
        return {"model_calls": dict(Counter(o.unit.provider for o in todo if o.unit.provider)),
                "local_renders": sum(1 for o in todo if not o.unit.provider)}

    # log
    def _log(self, event: str, proposal: dict, **fields) -> dict:
        record = {"ts": utc_now(), "event": event, "proposal": proposal["id"], "actor": proposal["actor"],
                  "kinds": proposal["kinds"], "autonomy": proposal["autonomy"], **fields}
        append_jsonl(self.log_path, record)
        return record

    def record(self, event: str, **fields) -> dict:
        """A decision that isn't about a proposal: a gate passed, a draft edited by hand, v1 adopted."""
        record = {"ts": utc_now(), "event": event, **fields}
        append_jsonl(self.log_path, record)
        return record

    def _save(self, proposal: dict) -> None:
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self._proposal_path(proposal["id"]).write_text(
            json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _next_id(self) -> str:
        n = len(list(self.proposals_dir.glob("P-*.json"))) if self.proposals_dir.exists() else 0
        return f"P-{n + 1:04d}"

    def load(self, pid: str) -> dict:
        path = self._proposal_path(pid)
        if not path.exists():
            raise DecisionError(f"no proposal {pid} in {self.proposals_dir}")
        return json.loads(path.read_text(encoding="utf-8"))

    def all(self) -> list[dict]:
        if not self.proposals_dir.exists():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.proposals_dir.glob("P-*.json"))]

    def waiting(self) -> list[dict]:
        """Proposals waiting for Y: pending ones, and ones applied under veto that Y hasn't confirmed."""
        return [p for p in self.all() if p["status"] == "pending"
                or (p["status"] == "applied" and not p.get("confirmed"))]

    def history(self) -> list[dict]:
        return read_jsonl(self.log_path)

    # ---------- the four verbs ----------

    def propose(self, actor: str, patch: list[dict], rationale: str = "", evidence: dict | None = None) -> dict:
        """Check a proposal and file it. Returns the proposal; its `status` says what happened:
        refused, pending, or applied (under veto or auto autonomy, or because Y proposed it)."""
        before = self.read_storyboard()
        proposal: dict[str, Any] = {
            "id": self._next_id(), "created": utc_now(), "actor": actor, "rationale": rationale,
            "evidence": evidence or {}, "patch": patch, "base_sha": storyboard_sha(before),
            "kinds": [], "autonomy": "propose", "changes": [], "status": "pending"}
        errors: list[str] = []
        try:
            after = patches.apply(before, patch)
        except PatchError as e:
            after, errors = None, [str(e)]
        if after is not None:
            changes = patches.diff(before, after)
            if not changes:
                errors.append("the patch changes nothing")
            proposal["changes"] = [{"path": p, "before": _encode(a), "after": _encode(b)} for p, a, b in changes]
            proposal["kinds"] = sorted({self.policy.kind_of(actor, p) for p, _, _ in changes})
            proposal["autonomy"] = "auto" if actor == HUMAN else self.policy.autonomy_of(proposal["kinds"])
            errors += ownership_errors(self.policy, actor, changes)
            if not errors:
                report = self.validate(after)
                errors += report.errors
                proposal["warnings"] = report.warnings
        if errors:
            proposal.update(status="refused", errors=errors)
            self._save(proposal)
            self._log("refused", proposal, errors=errors, paths=[c["path"] for c in proposal["changes"]])
            return proposal

        proposal["price"] = self.price(after)
        self._save(proposal)
        self._log("proposed", proposal, rationale=rationale, evidence=proposal["evidence"], patch=patch,
                  price=proposal["price"])
        if proposal["autonomy"] in ("veto", "auto"):
            by = HUMAN if actor == HUMAN else f"autonomy:{proposal['autonomy']}"
            self._apply(proposal, by=by, event="applied", confirmed=proposal["autonomy"] == "auto")
        return proposal

    def approve(self, pid: str, why: str = "", by: str = HUMAN) -> dict:
        proposal = self.load(pid)
        if proposal["status"] == "applied" and not proposal.get("confirmed"):
            proposal["confirmed"] = True
            self._save(proposal)
            self._log("confirmed", proposal, by=by, why=why)
            return proposal
        if proposal["status"] != "pending":
            raise DecisionError(f"{pid} is {proposal['status']}, not pending")
        return self._apply(proposal, by=by, event="approved", why=why, confirmed=True)

    def reject(self, pid: str, why: str, by: str = HUMAN) -> dict:
        proposal = self.load(pid)
        if proposal["status"] == "applied":
            return self.revert(pid, why=why, by=by)
        if proposal["status"] != "pending":
            raise DecisionError(f"{pid} is {proposal['status']}, not pending")
        proposal["status"] = "rejected"
        self._save(proposal)
        self._log("rejected", proposal, by=by, why=why)
        return proposal

    def revert(self, pid: str, why: str = "", by: str = HUMAN) -> dict:
        proposal = self.load(pid)
        if proposal["status"] != "applied":
            raise DecisionError(f"{pid} is {proposal['status']}; only an applied proposal can be reverted")
        current = self.read_storyboard()
        view = patches.to_keyed(current)
        for c in proposal["changes"]:
            if patches.get(view, c["path"]) != _decode(c["after"]):
                raise DecisionError(f"{pid} can't be reverted: {c['path']} has changed since it was applied")
        for c in reversed(proposal["changes"]):
            patches.set_value(view, c["path"], _decode(c["before"]))
        restored = patches.from_keyed(view)
        report = self.validate(restored)
        if report.errors:
            raise DecisionError(f"reverting {pid} would leave an invalid storyboard: " + "; ".join(report.errors))
        self._write_storyboard(restored)
        proposal["status"] = "reverted"
        self._save(proposal)
        self._log("reverted", proposal, by=by, why=why,
                  storyboard_sha={"before": storyboard_sha(current), "after": storyboard_sha(restored)})
        return proposal

    def _apply(self, proposal: dict, by: str, event: str, why: str = "", confirmed: bool = False) -> dict:
        """Land a proposal on the current storyboard. Changes are re-checked value by value,
        so a proposal still applies after unrelated edits, and a stale one is refused."""
        current = self.read_storyboard()
        view = patches.to_keyed(current)
        for c in proposal["changes"]:
            if patches.get(view, c["path"]) != _decode(c["before"]):
                raise DecisionError(f"{proposal['id']} is stale: {c['path']} changed after it was proposed; "
                                    "reject it and propose again")
        for c in proposal["changes"]:
            patches.set_value(view, c["path"], _decode(c["after"]))
        after = patches.from_keyed(view)
        report = self.validate(after)
        if report.errors:
            raise DecisionError(f"{proposal['id']} no longer leaves a valid storyboard: " + "; ".join(report.errors))
        self._write_storyboard(after)
        proposal.update(status="applied", confirmed=confirmed)
        self._save(proposal)
        self._log(event, proposal, by=by, why=why,
                  storyboard_sha={"before": storyboard_sha(current), "after": storyboard_sha(after)})
        return proposal


def describe(value, width: int = 70) -> str:
    if value is MISSING:
        return "(absent)"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= width else text[: width - 1] + "…"


__all__ = ["Decisions", "DecisionError", "Policy", "HUMAN", "ORDER", "describe", "ownership_errors"]

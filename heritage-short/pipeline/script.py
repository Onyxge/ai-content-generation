"""Stage: script, the director agent (unit U4, not built yet).

It will draft storyboard.json from docs/story/brief.md with Gemini 3.8 Flash, constrained
by schema/storyboard.schema.json, lint the draft, and show a diff for Y to approve. It is
an authoring step, never part of `make film` (ADR-003), and it never calls a generation
model: its only output is a proposed edit to the contract (ADR-002)."""
from __future__ import annotations


def main() -> int:
    print("The director (unit U4) isn't built yet. See docs/01-plan.md §14.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

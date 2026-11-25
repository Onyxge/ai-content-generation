"""Prompt composition. The style block and each character's description travel with every
image prompt, because drift mostly comes from re-describing things differently each time."""
from __future__ import annotations


def image_prompt(sb: dict, text: str, character_ids=()) -> str:
    chars = {c["id"]: c for c in sb["characters"]}
    parts = [text.strip()]
    described = [f"{cid}: {chars[cid]['description']}" for cid in character_ids if cid in chars]
    if described:
        parts.append("Characters: " + "; ".join(described))
    parts.append("Style: " + sb["style"]["block"])
    return "\n".join(parts)

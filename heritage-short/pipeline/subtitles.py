"""English subtitles (SRT) timed to each language's narration. The English script is the
single source of meaning (ADR-015): it is the English narration, and it is also the
subtitle track of the Amharic film, unless a shot overrides it with `subtitle_en`."""
from __future__ import annotations

import re
from pathlib import Path


PUNCT = ",;:—–"


def _greedy_lines(words: list[str], max_chars: int) -> list[str]:
    lines, line = [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > max_chars:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def _wrap(words: list[str], max_chars: int, max_lines: int) -> str:
    """One card's text. Two-line cards break where the lines are most even, preferring a
    break after a comma; anything else wraps greedily."""
    text = " ".join(words)
    if len(text) <= max_chars or max_lines < 2 or len(words) < 2:
        return text
    best, best_cost = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) > max_chars or len(b) > max_chars:
            continue
        cost = max(len(a), len(b)) - (8 if a[-1] in PUNCT else 0)
        if best_cost is None or cost < best_cost:
            best, best_cost = f"{a}\n{b}", cost
    return best or "\n".join(_greedy_lines(words, max_chars))


def _groups(words: list[str], max_chars: int, max_lines: int) -> list[list[str]]:
    """Split a sentence into the fewest cards that fit, with card lengths as even as
    possible and a preference for breaking after punctuation, so no word is left alone."""
    n = len(words)
    fits = {(i, j): len(_greedy_lines(words[i:j], max_chars)) <= max_lines
            for i in range(n) for j in range(i + 1, n + 1)}
    for k in range(1, n + 1):
        target = len(" ".join(words)) / k
        best = {(0, 0): (0.0, 0)}                       # (cards used, words used) -> (cost, previous split)
        for c in range(1, k + 1):
            for j in range(c, n + 1):
                for i in range(c - 1, j):
                    if (c - 1, i) not in best or not fits[(i, j)]:
                        continue
                    cost = ((len(" ".join(words[i:j])) - target) / max_chars) ** 2
                    if j < n and words[j - 1][-1] in PUNCT:
                        cost -= 0.3
                    total = best[(c - 1, i)][0] + cost
                    if (c, j) not in best or total < best[(c, j)][0]:
                        best[(c, j)] = (total, i)
        if (k, n) in best:
            groups, j = [], n
            for c in range(k, 0, -1):
                i = best[(c, j)][1]
                groups.append(words[i:j])
                j = i
            return groups[::-1]
    return [[w] for w in words]


def chunks(text: str, max_chars: int = 42, max_lines: int = 2) -> list[str]:
    """Split text into subtitle cards: each sentence starts a new card, a line holds at
    most `max_chars` characters, and a card holds at most `max_lines` lines."""
    cards: list[str] = []
    for sentence in (p.strip() for p in re.split(r"(?<=[.!?;:])\s+", text.strip())):
        if sentence:
            cards += [_wrap(g, max_chars, max_lines) for g in _groups(sentence.split(), max_chars, max_lines)]
    return cards


def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def subtitle_text(shot: dict) -> str:
    return (shot.get("subtitle_en") or shot["narration"].get("en") or "").strip()


def write_srt(sb: dict, timeline: dict, path: Path, max_chars: int = 42, max_lines: int = 2) -> int:
    """Write the SRT for one language's timeline; returns the number of cards."""
    shots = {s["id"]: s for s in sb["shots"]}
    cards: list[tuple[float, float, str]] = []
    for entry in timeline["shots"]:
        spoken = entry.get("narration")
        if not spoken:
            continue
        parts = chunks(subtitle_text(shots[entry["id"]]), max_chars, max_lines)
        if not parts:
            continue
        total = sum(len(p) for p in parts)
        t = spoken["start"]
        for part in parts:                      # each card's time is proportional to its length
            d = spoken["duration"] * len(part) / total
            cards.append((t, t + d, part))
            t += d
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(cards, 1):
            f.write(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n")
    return len(cards)

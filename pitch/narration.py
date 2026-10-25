"""The narration script, loaded from narration.json.

Beats live in JSON so the recorder (JS) and the assembler (Python) read one
source of truth. Each phrase becomes exactly one caption card and is
synthesised as its own audio file, so every cue in the final captions comes
from a measured wav length rather than an estimate.
"""
from __future__ import annotations

import json
from pathlib import Path

BEATS: list[dict] = json.loads((Path(__file__).parent / "narration.json").read_text())["beats"]


def all_phrases():
    """Yield (beat id, caption text, text to speak)."""
    for b in BEATS:
        for p in b["phrases"]:
            if isinstance(p, dict):
                yield b["id"], p["text"], p.get("say", p["text"])
            else:
                yield b["id"], p, p


if __name__ == "__main__":
    n = sum(len(b["phrases"]) for b in BEATS)
    chars = [len(c) for _, c, _ in all_phrases()]
    print(f"{len(BEATS)} beats, {n} caption cards")
    print(f"longest card: {max(chars)} chars ({max(chars) // 42 + 1} lines at 42)")
    for b in BEATS:
        print(f"  {b['id']:10s} {len(b['phrases']):2d} cards  {b['nav']}")

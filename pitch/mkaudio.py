"""Synthesise every caption phrase and record how long each one is.

Durations come from the rendered wavs, so the caption cues written later land
exactly on the words.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from narration import all_phrases
from tts import synth

AUDIO = Path(__file__).parent / "audio"


def main() -> None:
    AUDIO.mkdir(exist_ok=True)
    only = set(sys.argv[1:])

    durations: dict[str, float] = {}
    for i, (beat_id, caption, say) in enumerate(all_phrases()):
        name = f"p{i:02d}"
        if only and name not in only and beat_id not in only:
            continue
        out = AUDIO / f"{name}.wav"
        d = synth(say, out)
        durations[name] = round(d, 3)
        print(f"[audio] {name} {beat_id:10s} {d:5.2f}s  {caption[:52]}", flush=True)

    # Merge, never overwrite. A partial run (mkaudio.py p07) used to rewrite
    # every other entry with duration=null, which silently broke the assembler's
    # timing for the whole film.
    path = AUDIO / "durations.json"
    prev = {}
    if path.exists():
        try:
            prev = {p["id"]: p.get("duration") for p in json.loads(path.read_text())["phrases"]}
        except Exception:  # noqa: BLE001 -- a corrupt cache is not fatal
            prev = {}
    meta = {
        "phrases": [
            {
                "id": f"p{i:02d}",
                "beat": b,
                "text": c,
                "duration": durations.get(f"p{i:02d}", prev.get(f"p{i:02d}")),
            }
            for i, (b, c, _s) in enumerate(all_phrases())
        ]
    }
    path.write_text(json.dumps(meta, indent=2))
    total = sum(v for v in durations.values() if v)
    print(f"[audio] {len(durations)} phrases, {total:.1f}s of speech")


if __name__ == "__main__":
    main()

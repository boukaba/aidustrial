"""Tighten the silence at the tail of each phrase.

Every phrase carries a fixed gap so the voice does not run together. Across
fifty cards that fixed gap adds up to a lot of dead air, and a demo loses pace.
This trims each tail down to a tighter uniform gap without touching a single
spoken word -- nothing is re-synthesised, so the voice is bit-identical.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

GAP_S = 0.22
THRESH = 0.008
AUDIO = Path(__file__).parent / "audio"


def main() -> None:
    before = after = 0.0
    for w in sorted(AUDIO.glob("p*.wav")):
        a, sr = sf.read(str(w), dtype="float32")
        if a.ndim > 1:
            a = a[:, 0]
        before += len(a) / sr
        loud = np.where(np.abs(a) > THRESH)[0]
        if len(loud):
            a = a[: min(len(a), loud[-1] + int(sr * GAP_S))]
        after += len(a) / sr
        sf.write(str(w), a, sr)

    meta = json.loads((AUDIO / "durations.json").read_text())
    for ph in meta["phrases"]:
        a, sr = sf.read(str(AUDIO / f"{ph['id']}.wav"), dtype="float32")
        if a.ndim > 1:
            a = a[:, 0]
        ph["duration"] = round(len(a) / sr, 3)
    (AUDIO / "durations.json").write_text(json.dumps(meta, indent=2))

    per: dict[str, float] = defaultdict(float)
    for ph in meta["phrases"]:
        per[ph["beat"]] += ph["duration"]
    print(f"speech {before:.1f}s -> {after:.1f}s")
    for k, v in per.items():
        print(f"  {k:10s} {v:6.2f}s")
    print(f"total {sum(per.values()):.1f}s")


if __name__ == "__main__":
    main()

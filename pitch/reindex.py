"""Recompute durations.json from the wavs on disk.

The wavs are the source of truth. This rebuilds the timing table from them,
which also repairs a durations.json that a partial run clobbered.
"""
from __future__ import annotations

import json
from pathlib import Path

import soundfile as sf

from narration import all_phrases

AUDIO = Path(__file__).parent / "audio"

rows = []
for i, (beat, caption, _say) in enumerate(all_phrases()):
    pid = f"p{i:02d}"
    wav = AUDIO / f"{pid}.wav"
    if not wav.exists():
        raise SystemExit(f"missing {wav}")
    a, sr = sf.read(str(wav), dtype="float32")
    if getattr(a, "ndim", 1) > 1:
        a = a[:, 0]
    rows.append({"id": pid, "beat": beat, "text": caption, "duration": round(len(a) / sr, 3)})

(AUDIO / "durations.json").write_text(json.dumps({"phrases": rows}, indent=2))
print(f"reindexed {len(rows)} phrases, total {sum(r['duration'] for r in rows):.1f}s")

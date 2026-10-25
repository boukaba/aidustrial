"""Qwen3-TTS voice cloning for the pitch narration.

The reference clip is the speaker's own voice, so every line is generated in
that voice rather than a stock one. Cloning needs *both* the reference audio and
its transcript -- with only the audio the model has nothing to align against.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
REF_AUDIO = "/Users/YACINE/aidustrial/_ref_normalized.wav"
REF_TEXT = (ROOT / "ref_text.txt").read_text().strip()

#: 1.7B at 8-bit is the best-sounding clone that still fits comfortably in
#: unified memory. 0.6B is faster but noticeably flatter on long sentences.
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"

#: Silence appended to each phrase. This is the only pause control we have:
#: `generate` emits one continuous take per call, so pacing is done by
#: concatenating separately-synthesised phrases with a known tail.
GAP_S = 0.26

_model = None


def _load():
    global _model
    if _model is None:
        import time

        from mlx_audio.tts.utils import get_model_path, load_model

        t0 = time.perf_counter()
        _model = load_model(get_model_path(MODEL))
        print(f"[tts] loaded {MODEL} in {time.perf_counter() - t0:.1f}s", file=sys.stderr)
    return _model


def synth(text: str, out_path: str | Path, gap: float = GAP_S) -> float:
    """Render one phrase to a wav and return its duration in seconds."""
    import mlx.core as mx

    m = _load()
    chunks = []
    for res in m.generate(
        text,
        voice=None,
        ref_audio=REF_AUDIO,
        ref_text=REF_TEXT,
        split_pattern="\n",
        max_tokens=1200,
        stream=False,
    ):
        a = np.asarray(res.audio).reshape(-1)
        if a.size:
            chunks.append(a)

    if not chunks:
        raise RuntimeError(f"no audio produced for: {text[:60]}")

    audio = np.concatenate(chunks).astype(np.float32)
    sr = int(getattr(m, "sample_rate", 24000))
    if gap > 0:
        audio = np.concatenate([audio, np.zeros(int(sr * gap), dtype=np.float32)])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, sr)
    return len(audio) / sr

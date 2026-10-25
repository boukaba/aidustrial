"""Assemble the pitch video: screen beats + cloned voice + burned captions.

Each beat is cut to exactly its narration length, scaled to 1080p, and burned
with one caption card per phrase. Cue times are the measured wav lengths, so
the words and the captions cannot drift -- there is no estimated-from-text
timing anywhere in this file.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

from narration import BEATS

ROOT = Path(__file__).parent
AUDIO = ROOT / "audio"
OUT = ROOT / "out"
CAPS = ROOT / "captions"
#: Closing card: logo, creator and the copyright notice. Rendered from
#: endcard.html so the notice travels with the file, not only the repo.
ENDCARD = ROOT / "endcard.png"

#: The Homebrew ffmpeg here is built without libass, so it has no `ass`,
#: `subtitles` or `drawtext` filter at all. imageio-ffmpeg ships a full build
#: that does, which is what makes burned-in captions possible.
FFMPEG = subprocess.run(
    ["python3", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
    capture_output=True, text=True,
).stdout.strip() or "ffmpeg"

#: Fraction of a Cap window capture that is the macOS title bar. Measured on
#: this machine: a 675px-tall window has a 32px bar.
TITLE_BAR_RATIO = 32 / 675


#: Container metadata. YouTube reads title and description from the upload
#: form, not the file, but platforms and archives that read the container get
#: the same story, and it survives re-uploads. faststart moves the index to
#: the front so the file streams instead of downloading whole.
META = {
    "title": "Aidustrial: an agentic operations layer for large industrial farms",
    "artist": "Mohammed Boukaba",
    "author": "Mohammed Boukaba",
    "composer": "Mohammed Boukaba",
    "copyright": "\u00a9 2026 Mohammed Boukaba. All rights reserved.",
    "date": "2026",
    "genre": "Technology",
    "comment": (
        "Seven specialist AI Agents run a dairy complex around the clock against a "
        "live digital twin, and stop at a human gate before anything consequential. "
        "Built around a simulated site in Adrar, dimensioned from Baladna's published "
        "figures. Contact: mohammed@pullrun.dev"
    ),
    "description": (
        "Aidustrial is an agentic operations layer for large industrial farms. Seven "
        "specialist AI Agents work 24/7, deciding in under a second and escalating "
        "consequential decisions to humans with the evidence, the blast radius and the "
        "cost of doing nothing. Each AI Agent answers from its live readings, a cited "
        "document corpus and its own decision history. The demo runs on a simulated "
        "dairy complex in Adrar, Algerian Sahara, dimensioned from published Baladna "
        "figures; it is not affiliated with Baladna. Presenter: Mohammed Boukaba."
    ),
    "keywords": (
        "Aidustrial, AI Agents, multi-agent systems, human-in-the-loop, HITL, agentic AI, "
        "digital twin, RAG, retrieval augmented generation, industrial automation, "
        "dairy farming, precision agriculture, Baladna, Adrar, Algeria, LangGraph, "
        "FastAPI, Next.js, Jev, DeepSeek"
    ),
    "synopsis": (
        "Seven AI Agents run a large farm around the clock and stop at a human gate "
        "before anything consequential."
    ),
    "encoder": "Aidustrial pitch pipeline",
}

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Netflix,Arial,56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,180,180,64,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _t(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    return f"{h}:{m:02d}:{sec % 60:05.2f}"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{r.stderr[-1400:]}")


def _height(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip() or 0)


def _duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def build_captions(phrases: list[dict], ass_path: Path) -> None:
    """One card per phrase, held until the next one starts."""
    lines = [ASS_HEADER]
    for i, p in enumerate(phrases):
        start = p["start"]
        end = phrases[i + 1]["start"] if i + 1 < len(phrases) else p["start"] + p["duration"]
        lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Netflix,,0,0,0,,{p['text'].strip()}\n")
    ass_path.write_text("".join(lines))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    CAPS.mkdir(exist_ok=True)

    meta = json.loads((AUDIO / "durations.json").read_text())
    by_beat: dict[str, list[dict]] = defaultdict(list)
    for p in meta["phrases"]:
        by_beat[p["beat"]].append(p)
    idx = {p["id"]: i for i, p in enumerate(meta["phrases"])}

    beat_files: list[Path] = []
    for beat in BEATS:
        bid = beat["id"]
        phrases = by_beat[bid]

        cursor = 0.0
        for p in phrases:
            p["start"] = round(cursor, 3)
            cursor += p["duration"]
        beat_len = cursor

        # 1. narration for this beat
        beat_wav = AUDIO / f"beat_{bid}.wav"
        listing = AUDIO / f"_concat_{bid}.txt"
        names = [(AUDIO / ("p%02d.wav" % idx[p["id"]])).name for p in phrases]
        listing.write_text("".join(f"file '{n}'\n" for n in names))
        _run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
              "-i", str(listing), "-c", "copy", str(beat_wav)])
        listing.unlink()

        # 2. captions, timed against this beat's own audio
        build_captions(phrases, CAPS / f"{bid}.ass")

        # 3. video: drop the window title bar, centre-crop to 16:9, scale,
        # then burn captions. The take is the narration length plus a small
        # lead-in, so we trim from the front.
        src = OUT / f"{bid}.mp4"
        dst = OUT / f"{bid}_final.mp4"
        bar = round(_height(src) * TITLE_BAR_RATIO)
        _run([
            FFMPEG, "-v", "error", "-y",
            "-i", str(src),
            "-i", str(beat_wav),
            "-ss", "0.30", "-t", f"{beat_len:.3f}",
            "-vf",
            f"crop=iw:ih-{bar}:0:{bar},"
            f"crop=iw:iw*9/16:0:(ih-iw*9/16)/2,"
            "scale=1920:1080:flags=lanczos,"
            f"ass=captions/{bid}.ass",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            str(dst),
        ], cwd=ROOT)
        beat_files.append(dst)
        print(f"[asm] {bid:10s} {beat_len:5.2f}s  -> {dst.name}", flush=True)

    # End card, as a still with silence, so the copyright is in the video.
    if ENDCARD.exists():
        card = OUT / "_endcard.mp4"
        _run([
            FFMPEG, "-v", "error", "-y",
            "-loop", "1", "-i", str(ENDCARD),
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", "4", "-r", "30",
            "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            str(card),
        ])
        beat_files.append(card)
        print(f"[asm] endcard    4.00s  -> {card.name}", flush=True)

    concat = OUT / "_concat.txt"
    concat.write_text("".join(f"file '{p.name}'\n" for p in beat_files))
    final = ROOT / "aidustrial_pitch.mp4"
    meta_args: list[str] = []
    for k, v in META.items():
        meta_args += ["-metadata", f"{k}={v}"]

    _run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
          "-i", "_concat.txt", "-c", "copy",
          # use_metadata_tags keeps the non-standard keys (description,
          # synopsis, keywords) instead of silently dropping them.
          "-movflags", "use_metadata_tags+faststart",
          *meta_args, str(final)], cwd=OUT)
    concat.unlink()
    print(f"[asm] final: {final}  ({_duration(final):.2f}s)")


if __name__ == "__main__":
    main()

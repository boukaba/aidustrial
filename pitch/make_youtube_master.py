"""Build the high-bitrate master to upload to YouTube.

Why this exists: the normal master is encoded for local playback, where 1.0 to
1.6 Mbps at 1080p is plenty for a dark UI. YouTube does not see it that way. It
builds its rendition ladder from the uploaded file, and its guidance for 1080p
SDR is 8 Mbps. Uploaded below that, the high-resolution renditions it produces
carry so little extra detail over 240p that its adaptive player never bothers
climbing to them, which is exactly the "stuck at 240p" behaviour.

The fix is a master encoded far above the floor, at 1440p. Uploading 1440p also
makes YouTube's *1080p* rendition better, because it allocates a higher bitrate
ladder to higher-resolution sources. That is the standard remedy for text-heavy
screen recordings.

Run after assemble.py. Output: aidustrial_pitch_youtube.mp4
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "aidustrial_pitch.mp4"
DST = ROOT / "aidustrial_pitch_youtube.mp4"

FFMPEG = subprocess.run(
    ["python3", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
    capture_output=True, text=True,
).stdout.strip() or "ffmpeg"

#: 1440p at a forced 10 Mbps. Padding, strictly speaking, but YouTube's
#: rendition ladder is built from the uploaded bitrate, and its guidance for
#: 1080p SDR is 8 Mbps. Uploading well under that is what produces the
#: "stuck at 240p" default.
SCALE = "scale=2560:1440:flags=lanczos"

META = {
    "title": "Aidustrial: an agentic operations layer for large industrial farms",
    "artist": "Mohammed Boukaba",
    "author": "Mohammed Boukaba",
    "composer": "Mohammed Boukaba",
    "copyright": "\u00a9 2026 Mohammed Boukaba. All rights reserved.",
    "date": "2026",
    "genre": "Technology",
    "description": (
        "Aidustrial is an agentic operations layer for large industrial farms. Seven "
        "specialist AI Agents work 24/7, deciding in under a second and escalating "
        "consequential decisions to humans. The demo runs on a simulated dairy complex "
        "in Adrar, Algerian Sahara. Presenter: Mohammed Boukaba."
    ),
    "comment": "Contact: mohammed@pullrun.dev",
}


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}; run assemble.py first")

    args = [
        FFMPEG, "-v", "error", "-y", "-i", str(SRC),
        "-vf", f"{SCALE},format=yuv420p",
        # A target bitrate, not a quality target. This content compresses to
        # under 2 Mbps at CRF 16 because it is a dark UI with large flat areas,
        # so CRF never reaches the number YouTube expects to see.
        "-c:v", "libx264", "-preset", "slow",
        "-b:v", "10M", "-maxrate", "12M", "-bufsize", "24M",
        "-profile:v", "high", "-level", "5.1",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
    ]
    for k, v in META.items():
        args += ["-metadata", f"{k}={v}"]
    args.append(str(DST))
    subprocess.run(args, check=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,bit_rate",
         "-show_entries", "format=size", "-of", "default=nw=1", str(DST)],
        capture_output=True, text=True,
    ).stdout
    print(probe.strip())
    mb = DST.stat().st_size / 1_000_000
    print(f"[yt] {DST.name}: {mb:.0f} MB")


if __name__ == "__main__":
    main()

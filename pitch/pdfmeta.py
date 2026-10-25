"""Stamp the deck's document properties.

Chromium writes the PDF but ignores the author/subject options Playwright
passes through, so the fields are set on the file afterwards. A deck that
circulates as "Untitled" in a judge's downloads folder is a small thing that
looks careless.

Usage:  python3 pdfmeta.py [file.pdf]
"""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

META = {
    "/Title": "Aidustrial — Pitch Deck",
    "/Author": "Mohammed Boukaba",
    "/Subject": (
        "An agentic operations layer for large industrial farms: seven specialist "
        "AI Agents working 24/7, escalating consequential decisions to humans."
    ),
    "/Keywords": "Aidustrial, AI Agents, human-in-the-loop, digital twin, RAG, Baladna, Adrar, Thirduni",
    "/Creator": "Aidustrial",
    "/Producer": "Aidustrial pitch pipeline",
}


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "Aidustrial_pitch_deck.pdf")
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata(META)

    tmp = path.with_suffix(".meta.pdf")
    with tmp.open("wb") as fh:
        writer.write(fh)
    tmp.replace(path)

    back = PdfReader(str(path)).metadata or {}
    print(f"[pdf] {path.name} — {len(PdfReader(str(path)).pages)} pages")
    for k in ("/Title", "/Author", "/Subject"):
        print(f"      {k:9s} {back.get(k)}")


if __name__ == "__main__":
    main()

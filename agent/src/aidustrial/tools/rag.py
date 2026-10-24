"""Retrieval over the operational corpus.

Eight short documents cover the seven specialist domains plus the governance
rules. They are a *simulated* corpus, authored for this build, in the same way
the twin is simulated -- the set-up is declared as a simulation everywhere, so
there is nothing to dress up.

Retrieval is SQLite FTS5, which is built into Python's sqlite3. That choice is
deliberate: the corpus is dense with exact domain tokens (``PIVOT-3``, ``mm/s``,
``SCC``, ``dEHL``) that BM25 matches better than a small embedding model, it
costs no GPU or API call, and it cannot fail a container build by being unable
to download a model at start-up.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from . import ledger

#: Which documents each agent may retrieve from. A specialist answers from its
#: own domain; the governance document is readable by everyone.
AGENT_DOCS: dict[str, tuple[str, ...]] = {
    "agronomist": ("water-aquifer", "crop-irrigation", "governance-policy"),
    "crop": ("crop-irrigation", "water-aquifer", "governance-policy"),
    "veterinarian": ("heat-stress", "governance-policy"),
    "maintenance": ("pivot-maintenance", "governance-policy"),
    "logistics": ("feed-inventory", "governance-policy"),
    "milking": ("milking-quality", "governance-policy"),
    "calving": ("calving-youngstock", "governance-policy"),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc      TEXT PRIMARY KEY,
    title    TEXT,
    words    INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    doc UNINDEXED,
    section UNINDEXED,
    body,
    tokenize='porter unicode61'
);
"""

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(ledger.path()), timeout=5.0, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def configure() -> int:
    """Create the tables and ingest the corpus if it has not been loaded."""
    with _lock, _conn() as c:
        c.executescript(_SCHEMA)
        have = int(c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
    if have:
        return have
    return ingest()


def ingest(directory: str | Path | None = None) -> int:
    """Parse every markdown doc in the corpus and index it by section."""
    root = Path(directory) if directory else Path(__file__).resolve().parents[3] / "knowledge"
    if not root.is_dir():
        return 0

    rows: list[tuple[str, str, str]] = []
    docs: list[tuple[str, str, int]] = []
    for path in sorted(root.glob("*.md")):
        doc = path.stem
        text = path.read_text()
        title = doc.replace("-", " ").title()

        # Split into heading blocks first, then render. Doing this with a
        # closure over the loop variables would capture the last file's values.
        blocks: list[tuple[str, list[str]]] = [("Overview", [])]
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## "):
                blocks.append((line[3:].strip(), []))
            else:
                blocks[-1][1].append(line.strip())

        for section, body in blocks:
            joined = " ".join(" ".join(body).split())
            if joined:
                rows.append((doc, section, joined))
        docs.append((doc, title, len(text.split())))

    with _lock, _conn() as c:
        c.execute("DELETE FROM chunks")
        c.execute("DELETE FROM documents")
        c.executemany("INSERT INTO documents (doc, title, words) VALUES (?,?,?)", docs)
        c.executemany("INSERT INTO chunks (doc, section, body) VALUES (?,?,?)", rows)
    return len(rows)


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 expression (quoted terms joined by OR)."""
    terms = [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9]+", text.lower()) if len(t) > 2]
    # Dedupe, keep order, cap the expression so a long question cannot build an
    # enormous OR chain.
    seen: list[str] = []
    for t in terms:
        if t not in seen:
            seen.append(t)
    return " OR ".join(f'"{t}"' for t in seen[:24])


def _allowed(agent: str) -> tuple[str, ...]:
    return AGENT_DOCS.get(agent, ("governance-policy",))


def retrieve(agent: str, query: str, k: int = 3) -> list[dict[str, Any]]:
    """Top passages for this agent, restricted to its own domain documents."""
    expr = _fts_query(query)
    if not expr:
        return []
    docs = _allowed(agent)
    placeholders = ",".join("?" for _ in docs)
    with _lock, _conn() as c:
        rows = c.execute(
            f"""SELECT doc, section, body, bm25(chunks) AS score
                FROM chunks
                WHERE chunks MATCH ? AND doc IN ({placeholders})
                ORDER BY score LIMIT ?""",
            (expr, *docs, k),
        ).fetchall()
    return [
        {
            "doc": r["doc"],
            "section": r["section"],
            "text": r["body"],
            "cite": f"{r['doc'].upper()} §{r['section']}",
        }
        for r in rows
    ]


def corpus() -> list[dict[str, Any]]:
    """The documents available, for the UI and for the README."""
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM documents ORDER BY doc")]


def stats() -> dict[str, Any]:
    with _lock, _conn() as c:
        return {
            "documents": int(c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]),
            "chunks": int(c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]),
        }


__all__ = ["AGENT_DOCS", "configure", "corpus", "ingest", "retrieve", "stats"]

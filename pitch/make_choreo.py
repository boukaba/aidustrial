"""Generate choreography.json from the narration timings.

Actions are anchored to phrase boundaries measured from the rendered wavs, and
each move *starts* just before its phrase so the eased cursor travel finishes
as the narrator begins to speak the words. That is what keeps the pointer and
the voice in agreement instead of drifting a beat behind.

The spec below names real on-screen text (scraped from the running app), so a
target either resolves to the thing being discussed or the action is skipped --
it never silently points somewhere else.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

#: How long before its phrase a move begins. Roughly the eased travel time for
#: a normal distance, so the pointer settles exactly on the line.
LEAD = 0.85

#: beat -> list of steps. `p` is the phrase index. `t` is the element to point
#: at, `c` clicks it, `s` scrolls by pixels (with `n` wheel steps for a slow
#: crawl), `z` is an absolute scroll position. `off` delays within the phrase.
SPEC: dict[str, list[dict]] = {
    "home": [
        {"p": 0, "t": "The Adrar Dairy Farm"},
        {"p": 1, "t": "Food for the cows"},
        {"p": 2, "t": "New here? Take the 60-second tour"},
        {"p": 3, "t": "Food for the cows", "off": 0.3},
        {"p": 4, "s": 200, "n": 6},
        {"p": 5, "c": "What does this mean?"},
        {"p": 6, "z": 0},
    ],
    "infra": [
        {"p": 0, "t": "The underground water"},
        {"p": 1, "s": 240, "n": 7},
        {"p": 2, "t": "Cooling for the cows", "off": 0.4},
        {"p": 3, "z": 0},
    ],
    "agents": [
        {"p": 0, "t": "The seven specialists, working"},
        {"p": 1, "t": "deciding via"},
        {"p": 2, "t": "writing via"},
        {"p": 3, "t": "reading now"},
        {"p": 4, "s": 170, "n": 6},
        {"p": 5, "t": "Field agent"},
        {"p": 6, "t": "Water specialist"},
        {"p": 7, "t": "Cow doctor"},
        {"p": 8, "t": "Machine engineer"},
        {"p": 9, "t": "Milking agent"},
        {"p": 9, "t": "Calving agent", "off": 1.3},
        {"p": 9, "t": "Supply agent", "off": 2.6},
        {"p": 9, "c": "Reject", "off": 3.6},
    ],
    "orchestrator": [
        {"p": 0, "t": "The orchestrator"},
        {"p": 1, "s": 230, "n": 6},
        {"p": 2, "s": 230, "n": 6},
        {"p": 3, "t": "DISPATCH"},
        {"p": 4, "t": "BLACKBOARD"},
    ],
    "reasoning": [
        {"p": 0, "t": "deciding via"},
        {"p": 1, "t": "decided"},
        {"p": 2, "t": "decided", "off": 0.5},
        # On "the LLM writes the explanation, so you can argue with it", open
        # the maintenance agent and actually argue with it. The answer lands
        # during the next line, which is about risk belonging to us.
        {"p": 3, "do": "chat", "agentLabel": "Machine engineer",
         "ask": "Which pivot is closest to failure, and what does the manual say?"},
    ],
    "gate": [
        {"p": 0, "t": "Approve"},
        {"p": 1, "c": "Show technical detail and evidence"},
        {"p": 2, "t": "Reject"},
        {"p": 3, "c": "Reject", "off": 0.6},
    ],
    "cowfood": [
        {"p": 0, "t": "How the fields are doing overall"},
        {"p": 1, "t": "Why growing feed here is difficult"},
        {"p": 1, "s": 220, "n": 6, "off": 2.4},
        {"p": 2, "t": "FLD-A1"},
    ],
    "milk": [
        {"p": 0, "t": "How much milk"},
        {"p": 1, "t": "Is the milk kept cold?"},
    ],
    "herd": [
        {"p": 0, "t": "arrived by air"},
        {"p": 1, "t": "What is on the farm"},
        {"p": 2, "t": "Young cows getting ready to have calves"},
    ],
    "how": [
        {"p": 0, "t": "How the farm is run"},
        {"p": 1, "t": "Agent mesh"},
        {"p": 2, "s": 240, "n": 7},
    ],
    "close": [
        {"p": 0, "z": 0},
        {"p": 1, "t": "deciding via"},
        {"p": 2, "t": "writing via"},
        {"p": 3, "s": 200, "n": 6},
        {"p": 4, "t": "The seven specialists, working"},
        {"p": 5, "t": "reading now"},
        {"p": 6, "s": 220, "n": 7},
        {"p": 7, "t": "decided"},
        {"p": 8, "z": 0},
    ],
}


def main() -> None:
    dur = json.loads((ROOT / "audio" / "durations.json").read_text())["phrases"]
    per: dict[str, list[dict]] = defaultdict(list)
    for p in dur:
        per[p["beat"]].append(p)

    beats: dict[str, dict] = {}
    for beat, steps in SPEC.items():
        phrases = per[beat]
        out = []
        for st in steps:
            i = st["p"]
            if i >= len(phrases):
                continue
            start = sum(x["duration"] for x in phrases[:i]) + st.get("off", 0.0)
            if st.get("do") == "chat":
                out.append({"at": round(max(0.0, start - LEAD), 2), "do": "chat",
                            "agentLabel": st["agentLabel"], "ask": st["ask"]})
            elif "z" in st:
                # Scrolls should run *during* the phrase, not before it.
                at = max(0.0, start)
                out.append({"at": round(at, 2), "do": "scrollTo", "y": st["z"]})
            elif "s" in st:
                at = max(0.0, start)
                out.append({"at": round(at, 2), "do": "scroll", "dy": st["s"], "steps": st.get("n", 5)})
            elif "c" in st:
                out.append({"at": round(max(0.0, start - LEAD), 2), "do": "click", "target": st["c"]})
            else:
                out.append({"at": round(max(0.0, start - LEAD), 2), "do": "move", "target": st["t"]})
        out.sort(key=lambda a: a["at"])
        beats[beat] = {"actions": out}

    (ROOT / "choreography.json").write_text(
        json.dumps({"comment": "Generated by make_choreo.py from measured phrase timings.", "beats": beats}, indent=2)
    )
    n = sum(len(v["actions"]) for v in beats.values())
    print(f"choreography: {n} actions across {len(beats)} beats")


if __name__ == "__main__":
    main()

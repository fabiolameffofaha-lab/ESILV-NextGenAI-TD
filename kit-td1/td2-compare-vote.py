#!/usr/bin/env python3
"""TD 2, Step 1 (Pair A): fixed 2-of-3 panel versus 3-of-5 quorum on the stored TD 1 traces.

No network, no key. Reuses `proposals_for` and the student vote from atelier-vote.py,
so the 2-of-3 column is exactly what `atelier-vote.py --traces ... --case Cxx` prints.
The reference is read only AFTER each decision, to fill the agreement columns.

    python3 td2-compare-vote.py                                  # markdown table on stdout
    python3 td2-compare-vote.py --json ../reports/td2-vote.jsonl  # also the raw decisions
"""
import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("atelier_vote", HERE / "atelier-vote.py")
atelier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atelier)

PANEL_3 = list(atelier.PANEL)  # gpt-oss-120b, north-mini-code, qwen3.8-27b
PANEL_5 = PANEL_3 + [
    ("groq", "openai/gpt-oss-20b"),
    ("openrouter", "dots-studio/dots-3-note-preview:free"),
]
SHORT = {
    "openai/gpt-oss-120b": "120B",
    "cohere/north-mini-code:free": "North",
    "groq/qwen/qwen3.8-27b": "Qwen",
    "qwen/qwen3.8-27b": "Qwen",
    "openai/gpt-oss-20b": "20B",
    "dots-studio/dots-3-note-preview:free": "Dots",
}


def proposals(rows, case, panel):
    """Same rule as atelier-vote.proposals_for, for any panel: last CSV row per member."""
    saved = atelier.PANEL
    atelier.PANEL = panel
    try:
        return atelier.proposals_for(rows, case, "real")
    finally:
        atelier.PANEL = saved


def fmt_decision(d):
    if d["consensus"]:
        who = "+".join(SHORT[m.split(":", 1)[1]] for m in d["models"])
        return f"**{d['value']}** ({d['votes']} votes: {who})"
    return f"abstain (max {d['votes']})"


def agree(d, ref):
    if not d["consensus"]:
        return "—"
    return "yes" if d["value"] == ref else "**NO**"


def ballot(rows, case):
    """Last attempt of each of the five models, with the TD 1 verdict (read after the vote)."""
    last = {}
    for r in rows:
        if r["case_id"] == case and r["nature"] == "real":
            last[(r["provider"], r["model_requested"])] = r
    out = []
    for key in PANEL_5:
        r = last[key]
        v = r["value"] if r["value"] != "" else "∅"
        tag = r["verdict"] if r["verdict"] != "not_executed" else f"HTTP {r['http_status']}"
        out.append(f"{SHORT[key[1]]}={v} ({tag})")
    return "; ".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=HERE / "traces-td1.csv")
    parser.add_argument("--reference", type=Path, default=HERE / "reference-td1.csv")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    vote = atelier.load_vote()
    with args.traces.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with args.reference.open(encoding="utf-8", newline="") as f:
        refs = {r["case_id"]: int(r["revenue_cents"]) for r in csv.DictReader(f)}

    records = []
    print("| Q | Reference | 2-of-3 panel (k=2) | ref? | 3-of-5 quorum (k=3) | ref? | Changes? |")
    print("|---|---:|---|:-:|---|:-:|:-:|")
    for i in range(1, 21):
        case = f"C{i:02d}"
        d3 = vote(proposals(rows, case, PANEL_3), 2)   # decision first...
        d5 = vote(proposals(rows, case, PANEL_5), 3)
        ref = refs[case]                               # ...reference after
        changed = (d3["consensus"], d3["value"]) != (d5["consensus"], d5["value"])
        margin = d3["votes"] != d5["votes"] or changed
        flag = "decision" if changed else ("margin" if margin else "")
        print(f"| {case} | {ref} | {fmt_decision(d3)} | {agree(d3, ref)} | "
              f"{fmt_decision(d5)} | {agree(d5, ref)} | {flag} |")
        records.append({"case": case, "reference": ref, "panel_2_of_3": d3, "quorum_3_of_5": d5,
                        "ballot_5": ballot(rows, case), "change": flag or None})

    print("\nLast attempt per model (ballot of the 3-of-5 quorum, TD 1 verdict shown after the vote):\n")
    for r in records:
        print(f"- {r['case']}: {r['ballot_5']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

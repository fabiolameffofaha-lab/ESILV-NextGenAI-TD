#!/usr/bin/env python3
"""TD 2 (Pair C): routing simulator adapted to the TD 1 results of our sub-group.

Synthetic simulation, no API call, no key. The ELIGIBILITY LEVELS below are derived
from our own TD 1 table (model-question-comparison-en.csv, 100 cells); the prices come
from portefeuille-modeles-2026-09-28.csv / five-model-summary-en.csv. Quota availability
is a scenario, not measured. Twenty questions = batch-specific hypothesis, not a general rate.

Level 1: families F1 (period) and F3 (product list): 5/5 models at 100 %.
Level 2: + F2b (age at the order) and combined questions: only gpt-oss-120b and
         gpt-oss-20b at 100 % (F2b 1/1, combined 5/5 each; tiny n).
Level 3: + F2 (completed age at a date, C02/C08/C09/C11): only gpt-oss-120b at 100 % (4/4).
"""
import argparse
import json

# Fictional-envelope cost per request: 1000 input + 500 output tokens at OpenRouter's
# gpt-oss-120b price (0.15 / 0.60 USD per million) = 0.00045 USD.
PAID_COST = 0.00045

FAMILY_LEVEL = {"F1": 1, "F3": 1, "F2b": 2, "COMB": 2, "F2": 3}
FAMILY_CELLS = {
    "F1": "F1 period C01,C04,C05,C06,C07,C20",
    "F2": "F2 age@date C02,C08,C09,C11",
    "F2b": "F2b age@order C10",
    "F3": "F3 product C03,C12,C13,C14",
    "COMB": "combined C15-C19",
}

# TD 1 ratio (correct/cases) per resource and family. Source: pivot-models-questions-td1.md
RESOURCES = [
    {"id": "cohere/north-mini-code:free (OpenRouter)", "provider": "openrouter", "level": 1,
     "access": "free", "available": True, "cash": 0.0, "allocation": 0.0, "reset_minutes": None,
     "td1": {"F1": "6/6", "F3": "4/4", "F2": "1/4", "F2b": "0/1", "COMB": "1/5"}},
    {"id": "openai/gpt-oss-20b (Groq free)", "provider": "groq", "level": 2,
     "access": "free", "available": True, "cash": 0.0, "allocation": 0.0, "reset_minutes": None,
     "td1": {"F1": "6/6", "F3": "4/4", "F2": "1/4", "F2b": "1/1", "COMB": "5/5"}},
    {"id": "openai/gpt-oss-120b (Groq free)", "provider": "groq", "level": 3,
     "access": "free", "available": True, "cash": 0.0, "allocation": 0.0, "reset_minutes": None,
     "td1": {"F1": "6/6", "F3": "4/4", "F2": "4/4", "F2b": "1/1", "COMB": "5/5"}},
    {"id": "openai/gpt-oss-120b (OpenRouter paid)", "provider": "openrouter", "level": 3,
     "access": "tokens", "available": True, "cash": PAID_COST, "allocation": PAID_COST,
     "reset_minutes": None,
     "td1": {"F1": "6/6", "F3": "4/4", "F2": "4/4", "F2b": "1/1", "COMB": "5/5"}},
]


def required_checks(request):
    """Checking rule: (family, use) -> check. 'none' only for a dashboard AND a 100 % family."""
    fam, use = request.get("family"), request.get("use")
    if fam is None:  # original behaviour when no family is given
        return ("source verification and human review" if request["high_impact"]
                else "read-only execution and value check")
    if use == "payout":
        return "reference query re-executed + human review (no quorum alone)"
    if fam == "F2":  # C09: 3 of 5 models share the wrong value 0, a quorum elects it
        return "deterministic check (age-window script / reference query); quorum alone insufficient"
    if use == "customer":
        return "3-of-5 quorum" if fam in ("F2b", "COMB") else "2-of-3 quorum"
    if use == "dashboard":
        return "none" if fam in ("F1", "F3") else "2-of-3 quorum"
    return "review"


def choose(request, resources):
    """Same branch order as the supplied policy; only eligibility, checks and reason are enriched.

    Priority: (1) eligible included capacity (cash == 0, available), (2) defer for a free
    resource whose reset occurs before the deadline, (3) paid route within budget, (4) abstain.
    """
    eligible = [r for r in resources if r["level"] >= request["difficulty"]]
    checks = required_checks(request)
    fam = request.get("family")

    def cells(r):
        if fam is None:
            return ""
        return f" [TD1 {FAMILY_CELLS[fam]}: {r['td1'][fam]}]"

    included = [r for r in eligible if r["available"] and r["cash"] == 0]
    if included:
        chosen = min(included, key=lambda r: (r["allocation"], r["level"], r["id"]))
        return {"action": "run", "resource": chosen["id"], "cash": 0, "checks": checks,
                "reason": "eligible included capacity" + cells(chosen)}
    waiting = [r for r in eligible if not r["available"] and r["cash"] == 0
               and r["reset_minutes"] is not None
               and 0 < r["reset_minutes"] <= request["deadline_minutes"]]
    if waiting and request["can_wait"]:
        chosen = min(waiting, key=lambda r: r["reset_minutes"])
        return {"action": "defer", "resource": chosen["id"], "cash": 0, "checks": checks,
                "reason": "recheck availability at wake-up" + cells(chosen),
                "wake_in_minutes": chosen["reset_minutes"]}
    paid = [r for r in eligible if r["available"] and r["cash"] <= request["budget"]]
    if paid:
        chosen = min(paid, key=lambda r: (r["cash"], r["allocation"], r["id"]))
        return {"action": "run", "resource": chosen["id"], "cash": chosen["cash"], "checks": checks,
                "reason": "available route within the authorised budget" + cells(chosen)}
    return {"action": "abstain", "resource": None, "cash": 0, "checks": checks,
            "reason": "no eligible resource within deadline and budget"
                      + (f" [needs level {request['difficulty']} for {FAMILY_CELLS[fam]}]" if fam else "")}


def scenarios():
    base = {"difficulty": 1, "high_impact": False, "can_wait": True,
            "deadline_minutes": 120, "budget": 0.001}
    # Groq free-plan rate limit hit (HTTP 429 seen on qwen in TD 1): Groq models unavailable for 15 min.
    exhausted = [dict(r, available=False, reset_minutes=15) if r["provider"] == "groq" else dict(r)
                 for r in RESOURCES]

    def f(fam, use="dashboard", **kw):
        return {**base, "family": fam, "use": use, "difficulty": FAMILY_LEVEL[fam],
                "high_impact": use != "dashboard", **kw}

    return [
        ("simple", f("F1"), RESOURCES),
        ("complex", f("F2"), RESOURCES),
        ("deferrable", f("F2", can_wait=True), exhausted),
        ("urgent", f("F2", can_wait=False, deadline_minutes=5), exhausted),
        ("budget exhausted", f("F2", can_wait=False, budget=0), exhausted),
        ("high impact", f("F2", "payout"), RESOURCES),
        ("unknown capability", {**base, "family": "F2", "use": "dashboard", "difficulty": 4}, RESOURCES),
        ("F3 dashboard", f("F3"), RESOURCES),
        ("F1 customer figure", f("F1", "customer"), RESOURCES),
        ("combined customer figure", f("COMB", "customer"), RESOURCES),
        ("F2b customer, Groq 429", f("F2b", "customer"), exhausted),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", help="show only the named scenario")
    args = parser.parse_args()
    found = False
    for name, request, resources in scenarios():
        if args.scenario and name != args.scenario:
            continue
        found = True
        print(json.dumps({"scenario": name, "nature": "simulation", "request": request,
                          "result": choose(request, resources)}, ensure_ascii=False))
    if not found:
        parser.error("unknown scenario")


if __name__ == "__main__":
    main()

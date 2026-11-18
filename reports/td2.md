# TD 2 - The quorum, then the routing rule

Session of 18 November 2026. Raw material: the stored TD 1 traces
([`kit-td1/traces-td1.csv`](../kit-td1/traces-td1.csv), merged, 105 rows, nature `real`)
and [`kit-td1/reference-td1.csv`](../kit-td1/reference-td1.csv). **No new network call was made.**

| Pair | Step | Members |
|---|---|---|
| A | Step 1 - k-of-n vote, 2-of-3 vs 3-of-5 comparison | MaxouSpirou, Clmntphg |
| B | Step 2 - wrong consensus, SQL diagnosis | _(to fill)_ |
| C | Step 3 - routing rule, simulator | _(to fill)_ |

---

## Step 1 - The k-of-n vote (Pair A)

### 1.1 The method

`Orchestrateur.vote_k_sur_n` in
[`kit-td1/skeleton-multi-llm-en.py`](../kit-td1/skeleton-multi-llm-en.py) (section 7):

```python
n = len(traces_question)                      # n counts EVERY member, voting or not
if not (n // 2 < k <= n):
    raise ValueError("k must be a strict majority: n // 2 < k <= n")
seen = set()
for p in traces_question:                     # a duplicate is not a second vote
    key = (p.provider, p.model_requested)
    if key in seen:
        raise ValueError(f"duplicate proposal: {key}")
    seen.add(key)
votes = {}
for p in traces_question:                     # only executed proposals with a value vote
    if p.verdict == "executed" and p.value is not None:
        votes.setdefault(p.value, []).append(f"{p.provider}:{p.model_requested}")
best_value, best_models = max(votes.items(), key=lambda kv: len(kv[1]), default=(None, []))
if len(best_models) >= k:
    return {"consensus": True, "value": best_value, "votes": len(best_models), "models": best_models}
return {"consensus": False, "value": None, "votes": len(best_models), "models": []}
```

Design points (contract of the docstring):

- **n is fixed by the panel, not by who answered.** An HTTP 429 or an invalid SQL keeps its seat
  in n but casts no vote, so it makes the threshold *harder* to reach; it never lowers k.
- **Strict majority** `n // 2 < k <= n`: with k > n/2, two different values cannot both reach k,
  so the winner is unique. This is also why a tie (e.g. C10 below: 2 votes vs 2 votes in 3-of-5)
  can never produce a consensus: `max` may pick either value, but neither reaches k → abstain.
- **Duplicates refused**: the same (provider, model) twice would be one model voting twice.
- **No invented value**: below k the method returns `value: None`; it does not fall back to a
  plurality, an average or the "most plausible" value. The reference is never passed in.

Contract checks (run in a Python shell): two identical (provider, model) proposals →
`ValueError: duplicate proposal`; n=2, k=1 → `ValueError: k must be a strict majority`;
n=1, k=0 → same `ValueError`.

### 1.2 The four synthetic examples (`nature: simulation`, no network)

`python3 kit-td1/atelier-vote.py`

| Example | Values (120B, North, Qwen) | Ref | Decision k=2 | Matches ref |
|---|---|---:|---|:-:|
| agreement | 100, 100, 120 | 100 | consensus 100, 2 votes (120B + North) | yes |
| disagreement | 100, 110, 120 | 100 | abstain, max 1 vote | — |
| unavailable | 100, ∅, ∅ | 100 | abstain, max 1 vote (n stays 3) | — |
| wrong consensus | 0, 0, 100 | 100 | **consensus 0**, 2 votes (120B + North) | **no** |

"unavailable": the single surviving answer is the right one, yet the vote abstains, because
two seats out of three are empty. "wrong consensus": the vote faithfully elects a wrong value;
majority voting measures agreement, not correctness (see Step 2).

On one real question: `python3 kit-td1/atelier-vote.py --traces kit-td1/traces-td1.csv --case C02`
→ consensus 590320, 2 votes (120B + Qwen), `matches_reference: true` (North had `sql_invalid`).

### 1.3 Twenty-question comparison: fixed 2-of-3 panel vs 3-of-5 quorum

Produced by [`kit-td1/td2-compare-vote.py`](../kit-td1/td2-compare-vote.py), which re-uses
`proposals_for` from `atelier-vote.py` (same rule: the **last** CSV row of each member is its
last attempt; `correct`/`incorrect` + value → `executed`, anything else → `error`).
Raw decisions: [`reports/td2-vote-decisions.jsonl`](td2-vote-decisions.jsonl).

- **2-of-3 panel**, k = 2: `groq:openai/gpt-oss-120b` (120B), `openrouter:cohere/north-mini-code:free` (North), `groq:qwen/qwen3.8-27b` (Qwen).
- **3-of-5 quorum**, k = 3: the same three + `groq:openai/gpt-oss-20b` (20B) + `openrouter:dots-studio/dots-3-note-preview:free` (Dots).

| Q | Reference | 2-of-3 panel (k=2) | ref? | 3-of-5 quorum (k=3) | ref? | Change |
|---|---:|---|:-:|---|:-:|:-:|
| C01 | 792800 | **792800** (3: 120B+North+Qwen) | yes | **792800** (5: all) | yes | margin |
| C02 | 590320 | **590320** (2: 120B+Qwen) | yes | abstain (max 2) | — | **decision** |
| C03 | 936350 | **936350** (3: 120B+North+Qwen) | yes | **936350** (5: all) | yes | margin |
| C04 | 2826250 | **2826250** (3: 120B+North+Qwen) | yes | **2826250** (5: all) | yes | margin |
| C05 | 38480 | **38480** (3: 120B+North+Qwen) | yes | **38480** (5: all) | yes | margin |
| C06 | 0 | **0** (3: 120B+North+Qwen) | yes | **0** (5: all) | yes | margin |
| C07 | 13970 | **13970** (3: 120B+North+Qwen) | yes | **13970** (5: all) | yes | margin |
| C08 | 605580 | **605580** (2: 120B+Qwen) | yes | abstain (max 2) | — | **decision** |
| C09 | 487980 | **0** (2: North+Qwen) | **NO** | **0** (3: North+Qwen+Dots) | **NO** | margin |
| C10 | 558980 | abstain (max 1) | — | abstain (max 2, tie 2-2) | — | margin |
| C11 | 446690 | **446690** (3: 120B+North+Qwen) | yes | **446690** (4: 120B+North+Qwen+Dots) | yes | margin |
| C12 | 1666490 | **1666490** (3: 120B+North+Qwen) | yes | **1666490** (5: all) | yes | margin |
| C13 | 107740 | **107740** (3: 120B+North+Qwen) | yes | **107740** (5: all) | yes | margin |
| C14 | 0 | **0** (3: 120B+North+Qwen) | yes | **0** (5: all) | yes | margin |
| C15 | 168680 | abstain (max 1) | — | abstain (max 2) | — | margin |
| C16 | 376740 | **376740** (2: 120B+Qwen) | yes | **376740** (3: 120B+Qwen+20B) | yes | margin |
| C17 | 258180 | abstain (max 1) | — | abstain (max 2) | — | margin |
| C18 | 62480 | **62480** (3: 120B+North+Qwen) | yes | **62480** (4: 120B+North+Qwen+20B) | yes | margin |
| C19 | 1990 | abstain (max 1) | — | **1990** (3: 120B+20B+Dots) | yes | **decision** |
| C20 | 1106090 | **1106090** (3: 120B+North+Qwen) | yes | **1106090** (5: all) | yes | margin |

Ballots (last attempt of each model; the TD 1 verdict in brackets is read **after** the vote):

| Q | 120B | North | Qwen | 20B | Dots |
|---|---|---|---|---|---|
| C02 | 590320 (correct) | ∅ (**sql_invalid**) | 590320 (correct) | 0 (incorrect) | 135000 (incorrect) |
| C08 | 605580 (correct) | 1418380 (incorrect) | 605580 (correct) | 388500 (incorrect) | 186340 (incorrect) |
| C09 | 487980 (correct) | 0 (incorrect) | 0 (incorrect) | 487980 (correct) | 0 (incorrect) |
| C10 | 558980 (correct) | 0 (incorrect) | 119410 (incorrect) | 558980 (correct) | 0 (incorrect) |
| C11 | 446690 (correct) | 446690 (correct) | 446690 (correct) | 322160 (incorrect) | 446690 (correct) |
| C15 | 168680 (correct) | 314020 (incorrect) | 0 (incorrect) | 168680 (correct) | 138920 (incorrect) |
| C16 | 376740 (correct) | 0 (incorrect) | 376740 (correct, 2nd attempt after **HTTP 429**) | 376740 (correct) | 1447730 (incorrect) |
| C17 | 258180 (correct) | 371990 (incorrect) | 248490 (incorrect, 2nd attempt after **HTTP 429**) | 258180 (correct) | 0 (incorrect) |
| C18 | 62480 (correct) | 62480 (correct) | 62480 (correct, 2nd attempt after **HTTP 429**) | 62480 (correct) | 39580 (incorrect) |
| C19 | 1990 (correct) | 71640 (incorrect) | 83580 (incorrect, 2nd attempt after **HTTP 429**) | 1990 (correct) | 1990 (correct) |
| C20 | 1106090 (correct) | 1106090 (correct) | 1106090 (correct, 2nd attempt after **HTTP 429**) | 1106090 (correct) | 1106090 (correct) |

C01, C03-C07, C12-C14: all five models return the reference value (pure F1 period / F3 product
questions).

### 1.4 Every difference between 2-of-3 and 3-of-5, explained

**Decision changes (3 questions)**

- **C02 - consensus → abstention.** North's statement is `sql_invalid` (HTTP 200, but the SQL did
  not execute): it keeps its seat and casts no vote. In 2-of-3, 120B + Qwen = 2 votes for 590320
  = k → correct consensus. In 3-of-5 the same 2 votes are below k = 3, because the two added
  models answer two *different* wrong values (20B = 0, Dots = 135000). The invalid SQL costs one
  vote that the larger quorum needed. Safer (no wrong value), but the right answer is lost.
- **C08 - consensus → abstention.** 120B + Qwen = 2 votes for 605580 (correct). The three other
  models scatter on three different wrong values (North 1418380, 20B 388500, Dots 186340), so
  the best count stays 2 < 3. Same mechanism as C02: the added members bring no vote for the
  majority value.
- **C19 - abstention → consensus.** In the fixed panel the three values all differ
  (120B 1990, North 71640, Qwen 83580 - Qwen's value comes from its retry after an HTTP 429)
  → max 1 vote → abstain. In 3-of-5, 20B and Dots both return 1990: 120B + 20B + Dots = 3 = k →
  consensus on the reference. The two models outside the panel rescue the question.

**Margin-only changes (17 questions)** - same decision, different vote count:

- C01, C03-C07, C12-C14, C20: 3 → 5 votes, unanimity (F1 / F3 questions).
- C11: 3 → 4 votes; 20B's 322160 is the only dissent. C18: 3 → 4; Dots' 39580 dissents.
- **C16: 2 → 3 votes, exactly at k.** North (0) and Dots (1447730) are wrong; 20B joins
  120B + Qwen. The consensus survives in both quorums *only because Qwen's retry succeeded*.
- **C09: wrong consensus in both, and stronger in 3-of-5 (2 → 3 votes).** North, Qwen and Dots
  all return the same wrong value 0; the reference 487980 gets only 120B + 20B. Moving to 3-of-5
  does *not* protect: Dots adds a third vote for the wrong value. This is the shared wrong value
  handed to Pair B (Step 2).
- C10: abstain in both, max 1 → 2. In 3-of-5 it is a **2-2 tie**: 558980 (120B + 20B, correct)
  vs 0 (North + Dots, wrong). The strict majority prevents either from winning.
- C15, C17: abstain in both, max 1 → 2 (120B + 20B on the reference; the other three scatter).

**Sensitivity to the HTTP 429s.** Qwen hit `HTTP 429: Rate limit reached` on its first attempt
for C16-C20; its second attempt is the last CSV row and is the one that votes. Re-running with
the **first** attempt kept (Qwen unavailable, still in n): C16 becomes *abstain* in both
quorums (2-of-3 max 1, 3-of-5 max 2); C18 and C20 keep their consensus with one vote less
(2-of-3: 2 votes); C19 stays abstain / consensus 1990. So one rate limit is enough to turn a
correct decision (C16) into an abstention: availability is part of the quorum's reliability.

### 1.5 Summary

| | 2-of-3 panel | 3-of-5 quorum |
|---|---:|---:|
| Consensus | 16 / 20 | 15 / 20 |
| … equal to the reference | 15 | 14 |
| … **wrong** consensus | 1 (C09) | 1 (C09) |
| Abstentions | 4 (C10, C15, C17, C19) | 5 (C02, C08, C10, C15, C17) |
| Questions where the reference was available among the answers but the vote abstained | 4 | 5 |

Reading:

1. On this batch, 3-of-5 is **not** safer than 2-of-3: it keeps the same wrong consensus (C09,
   even with a larger margin), loses two correct answers (C02, C08) and gains one (C19).
   Adding members only helps if they are *independent and reliable on the family*: on the ten
   age questions (C02, C08-C11, C15-C19) 20B is correct 7 times out of 10, but Dots only 2 out of
   10 (C11, C19), and Dots shares the wrong 0 with North and Qwen on C09.
2. All disagreements are on F2 / F2b (age) questions and their combinations (C02, C08-C11,
   C15-C19). On F1 period and F3 product questions every model agrees with the reference: a
   quorum there only adds cost (useful input for Pair C's routing rule).
3. In every abstention the correct value was proposed by 120B (and often 20B). An abstention is
   the intended safe outcome: it defers to a deterministic check or human review rather than
   returning a number.
4. Limits: 20 questions, one batch, one run per model (plus Qwen's retries). This supports a
   batch-specific hypothesis, not a general error rate or a quorum error guarantee.

---

## Step 2 - The wrong consensus (Pair B)

_(Pair B to complete. Candidate from Step 1: **C09**, shared wrong value 0 from North, Qwen and
Dots; reference 487980; wins both the 2-of-3 panel (North + Qwen) and the 3-of-5 quorum
(North + Qwen + Dots). Second shared wrong value: **C10**, value 0 from North and Dots - outvoted:
Dots is not in the 2-of-3 panel, and in 3-of-5 it only reaches a 2-2 tie.)_

## Step 3 - The routing rule (Pair C)

_(Pair C to complete.)_

## Cross-review, contributions, limits and next steps

_(to complete after the 16:45 cross-review.)_

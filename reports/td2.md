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

Full standalone version: [`td2-step3-pair-c.md`](td2-step3-pair-c.md). TD 1 values are real traces; simulator outputs ([before](routage-before.jsonl), [after](routage-after.jsonl)) are **synthetic**. Adapted simulator: [`kit-td1/atelier-routage.py`](../kit-td1/atelier-routage.py) (original kept in `atelier-routage-original.py`).

### 3.1. Exact TD 1 rates per family (correct / cases)

Source: `kit-td1/pivot-models-questions-td1.md` (final status = last attempt). Families: F1 period = C01, C04, C05, C06, C07, C20 · F2 age on a date = C02, C08, C09, C11 · F2b age at the order = C10 · F3 product list = C03, C12, C13, C14 · Combined = C15–C19.

| Model (access, price) | F1 (6) | F2 (4) | F2b (1) | F3 (4) | Comb. (5) | Failures |
|---|---|---|---|---|---|---|
| gpt-oss-120b (Groq free; paid 0.15/0.60 $/M) | 6/6 | 4/4 | 1/1 | 4/4 | 5/5 | none |
| gpt-oss-20b (Groq free; paid 0.018/0.09) | 6/6 | **1/4** | 1/1 | 4/4 | 5/5 | C02, C08, C11 wrong |
| cohere/north-mini-code:free (OpenRouter free) | 6/6 | **1/4** | **0/1** | 4/4 | **1/5** | C02 invalid SQL; C08, C09, C10, C15, C16, C17, C19 wrong |
| qwen3.8-27b (Groq free; 5×HTTP 429 on C16–C20) | 6/6 | 3/4 | **0/1** | 4/4 | **2/5** | C09, C10, C15, C17, C19 wrong |
| dots-3-note-preview:free (OpenRouter free) | 6/6 | **1/4** | **0/1** | 4/4 | **1/5** | C02, C08, C09, C10, C15, C16, C17, C18 wrong |

Key reading: all five models are 100 % on **F1 and F3** (10 cells each); the errors are concentrated on age questions (F2, F2b) and on combinations that include an age filter. Only **gpt-oss-120b** is 100 % on F2 (4/4).

**Wrong values are sometimes shared**, so a quorum is not a safeguard on age questions: on **C09** (reference 487 980) cohere, qwen and dots all return **0** → 3 of 5 models agree on the wrong value, so both the 2-of-3 panel (120b, cohere, qwen → 0 twice) and the 3-of-5 quorum elect 0. On C10 cohere and dots share 0 (2 of 5, no 3-of-5 consensus).

### 3.2. The one-page rule

Costs of error: **dashboard** (internal, low), **customer figure** (shown outside), **payout** (money moves). "None" is allowed only for a dashboard *and* a family where the chosen model was 100 % in TD 1.

| Family | Cells / rate of the first model | First model (cheapest 100 % free) | Dashboard | Customer figure | Payout | If first model unavailable |
|---|---|---|---|---|---|---|
| F1 period | C01,C04,C05,C06,C07,C20 – 6/6 (all 5 models) | cohere/north-mini-code:free (cost 0; 50 req/day cap) | **none** | 2-of-3 quorum | reference query re-executed + review | next: gpt-oss-20b (Groq free, 6/6), then 120b; can wait → wait for refill |
| F3 product list | C03,C12,C13,C14 – 4/4 (all 5 models) | cohere/north-mini-code:free | **none** | 2-of-3 quorum | reference query + review | same as F1 |
| F2b age at the order | C10 – 1/1 for 120b and 20b (0/1 cohere, qwen, dots) | gpt-oss-20b (Groq free) | 2-of-3 quorum | 3-of-5 quorum + deterministic check | reference query + review | 120b Groq → wait for Groq reset → paid 120b only if budget allows → abstain |
| Combined (C15–C19) | 5/5 for 20b and 120b; 1/5 cohere, 2/5 qwen, 1/5 dots | gpt-oss-20b (Groq free) | 2-of-3 quorum | 3-of-5 quorum + deterministic check | reference query + review | as F2b |
| F2 age on a date | C02,C08,C09,C11 – 4/4 for 120b only (20b 1/4, qwen 3/4) | gpt-oss-120b (Groq free) | **deterministic check** (age-window script / reference SQL) | deterministic check (quorum alone insufficient: C09 shared 0) | reference query + review | wait for Groq refill (can wait) → paid 120b (≈0.00045 $/request) → abstain |

Rules common to all rows: (1) never "none" if the model made ≥1 error on the family (F2, F2b, Comb.) or if the figure goes to a customer or governs a payout; (2) a quorum only counts distinct families and a failed member stays in n (see Step 1); (3) no eligible resource within deadline and budget → **abstain**, never an invented value. Limits: F2b has 1 cell, Combined 5 cells; the 20b "100 %" on Comb./F2b is thin evidence, hence the checks above.

### 3.3. Simulator outputs

Files: `reports/routage-before.jsonl` (supplied simulator, `kit-td1/atelier-routage-original.py`) and `reports/routage-after.jsonl` (adapted `kit-td1/atelier-routage.py`). Both are **synthetic**.

Adaptation: `RESOURCES` replaced by four portfolio resources with levels derived from TD 1 (level 1 = F1/F3 → cohere free; level 2 = + F2b/Comb. → gpt-oss-20b Groq free; level 3 = + F2 → gpt-oss-120b Groq free, and its OpenRouter paid route at 0.00045 $/request for a 1000-in/500-out envelope). `choose` keeps the **same branch order**; it adds the checks from the table above and the TD 1 cells and ratio of the chosen resource to every `reason`. Scenario "exhausted" now means Groq rate limit (15 min reset, as the HTTP 429 seen on qwen).

| Scenario | Before (supplied) | After (adapted) |
|---|---|---|
| simple | run small-free | run cohere free; checks none; `[TD1 F1 … 6/6]` |
| complex | run senior-subscription | run gpt-oss-120b Groq free; deterministic check; `[TD1 F2 C02,C08,C09,C11: 4/4]` |
| deferrable | defer senior-subscription, wake 60 min | defer gpt-oss-120b Groq free, wake 15 min |
| urgent | run senior-api (0.30) | run 120b OpenRouter paid (0.00045) |
| budget exhausted | abstain | abstain `[needs level 3 for F2]` |
| high impact | run subscription, human review | run 120b Groq free; reference query re-executed + review |
| unknown capability (difficulty 4) | abstain | abstain `[needs level 4 …]` |
| *new* F3 dashboard / F1 customer / combined customer / F2b customer with Groq 429 | – | cohere none / cohere 2-of-3 / 20b 3-of-5 / defer 20b 15 min, 3-of-5 |

### 3.4. Why `choose` prefers an available included resource to deferring

In `choose` the branches run in this order: (1) `included` = eligible, `available`, `cash == 0`; (2) `waiting` → `defer`; (3) `paid` within budget; (4) abstain. A subscription with `cash == 0` and `allocation > 0` is `available`, so branch 1 returns `run` before branch 2 is even evaluated. The exhausted free resource (`available False`, `allocation == 0`) is only a candidate for branch 2.

Why this priority is sensible:
- **Zero marginal cash, zero delay**: the subscription is already paid, running now spends nothing new and meets any deadline; deferring costs time and the wake-up is only a *recheck* ("reaching a reset time does not prove that capacity is available").
- **Included capacity is perishable**: unused allocation is lost at reset, while a deferral keeps the request pending and can fail on recheck (then paid route or abstain).
- Among included resources the key `(allocation, level, id)` uses the one with least allocation and lowest level first, so small models are used before senior ones.

**When to reverse it** (prefer `defer` to the free resource although the subscription is available): when the request is nonurgent (`can_wait`, `deadline_minutes` clearly larger than `reset_minutes`) **and** the subscription allocation is scarce and must be reserved for requests that need it, i.e. remaining allocation is lower than the expected demand of high-impact / difficulty-3 requests before the next reset (or overage/shared-quota penalties apply), **and** the free resource is itself eligible (level ≥ difficulty, e.g. a TD 1 family where it is 100 %). Reversal is also right when the quorum needs an independent family and the free model provides it. It must **not** be reversed for urgent requests or when the free resource's reset is later than the deadline (the `waiting` filter already excludes it).

Note: in our adapted portfolio there is no subscription resource tested in TD 1 (Claude/Codex/Gemini subscriptions are in the portfolio but have no TD 1 cells), so the priority is exercised on the original simulator (scenarios `complex` vs `deferrable`) and, with the same branch order, on Groq free (included) vs Groq exhausted (defer) vs OpenRouter paid (run) in the adapted one.

### 3.5. Contribution and limits

- Pair C: rates per family, rule, adapted `RESOURCES`/`choose`, before/after outputs, analysis of `choose`.
- Limits: 20 questions, F2b = 1 cell; prices from `portefeuille-modeles-2026-09-28.csv` / `five-model-summary-en.csv` (OpenRouter list, 2026-10-21); the paid 120b cost is a fictional token envelope; availability is simulated.

## Cross-review, contributions, limits and next steps

_(to complete after the 16:45 cross-review.)_

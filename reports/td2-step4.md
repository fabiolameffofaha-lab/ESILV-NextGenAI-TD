# TD 2 - Step 4: plenary, what the three steps show together

Section to merge into `reports/td2.md`. Sources: Step 1 (Pair A, `reports/td2-vote-decisions.jsonl`),
Step 2 (Pair B, `reports/td2-step2-pair-b.md`), Step 3 (Pair C, `reports/td2-step3-pair-c.md`).
All figures come from the stored TD 1 traces (`kit-td1/traces-td1.csv`, last attempt of each model);
no new network call. Twenty questions support a batch-specific hypothesis, not a general error rate.

## 1. Our wrong consensus (presented in plenary)

**C09**: revenue of customers aged exactly 25 on 2026-09-26. Reference 487980.
cohere, qwen and dots all return **0**; only gpt-oss-120b and gpt-oss-20b are correct.

| Vote | Result |
|---|---|
| fixed 2-of-3 panel (120b, cohere, qwen) | consensus on 0 (cohere + qwen), wrong |
| 3-of-5 quorum (all five models) | consensus on 0 (cohere + qwen + dots), wrong |

The three wrong queries have three different SQL faults (cohere: age computed without `2026 -`;
qwen: an empty month-day window plus the order date instead of the reference date; dots: a single
birth day and a single order day). They agree because **0 is what any over-restrictive filter returns**
with `COALESCE(SUM(...), 0)`. A vote counts identical values, not identical reasoning.

## 2. How the three steps fit together

| Step | What it shows | What the next step takes from it |
|---|---|---|
| 1 - vote (Pair A) | On F1 and F3 every model agrees with the reference. All disagreements, abstentions and the wrong consensus are on age questions (C02, C08-C11, C15-C19). 3-of-5 is not safer than 2-of-3: it keeps C09 wrong, loses C02 and C08, gains C19. | Where to look for a shared wrong value: C09 and C10. |
| 2 - wrong consensus (Pair B) | On C09 the quorum elects a wrong value whatever its size; the cause is in the SQL filter, and a deterministic check (delta query, or recomputation from the CSV files) finds it. | A quorum alone is not acceptable on F2 (age at a date). |
| 3 - routing rule (Pair C) | Cheapest model per family: cohere free for F1/F3, gpt-oss-20b for F2b/Combined, gpt-oss-120b for F2. Checks grow with the cost of an error: none (dashboard, 100 % family), quorum, deterministic check, reference + review (payout). | F2 always gets a deterministic check (rule cites C09); a payout never relies on a quorum. |

The thread: **Step 1 locates the risk (age questions), Step 2 explains why a vote cannot remove it
(errors converge on 0), Step 3 prices it (a deterministic check instead of more votes).**

## 3. Questions for which no free model is enough on its own

All five TD 1 models were used on free routes. A model is "enough on its own" for a question only if
it can be called once, without checking, with no risk on that family. Per question, correct models
out of five:

| Question | Family | Correct models | 2-of-3 | 3-of-5 | Enough alone? |
|---|---|---|---|---|---|
| C01, C03-C07, C12-C14, C20 | F1 / F3 | 5/5 | correct | correct | yes: any model, even the cheapest |
| C11 | F2 | 4/5 (20b wrong) | correct | correct | no: 20b, the cheapest Groq model, fails |
| C18 | Combined (age at order) | 4/5 (dots wrong) | correct | correct | no |
| C16 | F3 + F2 | 3/5 (120b, qwen, 20b) | correct | correct | no |
| C19 | Combined | 3/5 (120b, 20b, dots) | abstain | correct | no |
| C02 | F2 | 2/5 (120b, qwen) | correct | abstain | no |
| C08 | F2 | 2/5 (120b, qwen) | correct | abstain | no |
| **C10** | F2b | 2/5 (120b, 20b) | abstain | abstain | **no, and no free quorum answers** |
| **C15** | Combined | 2/5 (120b, 20b) | abstain | abstain | **no, and no free quorum answers** |
| **C17** | Combined | 2/5 (120b, 20b) | abstain | abstain | **no, and no free quorum answers** |
| **C09** | F2 | 2/5 (120b, 20b) | **wrong** | **wrong** | **no, and every free quorum is wrong** |

Reading:

- **10 of the 20 questions** (all those with an age condition) have at least one free model that is
  wrong: on these, a single unchecked call is not acceptable for anything but an internal dashboard.
- **4 questions (C09, C10, C15, C17)** get no correct answer from any free quorum we tested: either
  abstention or, for C09, a wrong consensus. They set the price of checking for TD 3.
- gpt-oss-120b was correct on all 20, but that is one run on one batch; Step 3 still puts a
  deterministic check on F2 for it, because a single model gives no signal when it is wrong.

## 4. The price of checking (input for TD 3)

For the four questions above, the options are:

| Option | Cash cost | Other cost | Covers C09? |
|---|---|---|---|
| larger free quorum | 0 | more calls, rate limits (5 x HTTP 429 on qwen), more abstentions | no: the wrong 0 gains votes |
| deterministic check (reference SQL or age-window script, plus a `COUNT(*)` of the target population when the result is 0) | 0 | a query written and validated once per family by a person | yes |
| paid route of gpt-oss-120b (OpenRouter) | about 0.00045 USD per request (1000 in / 500 out tokens) | budget, still a single model | no proof on its own |
| human review | 0 cash | time; reserved for payouts | yes |

Our position for the plenary: on age questions, **checking is cheaper than voting**. The deterministic
check costs no tokens and is the only option that catches C09; extra votes cost calls and quota and
can make the wrong answer stronger.

## 5. Comparison with the other sub-groups' rules

_(Fill in during the plenary: for each other sub-group, its wrong consensus, its checking level per
family and the cost it accepts; note where its rule differs from ours and why.)_

# TD 2 – Step 3 (Pair C): the routing rule

> Section to merge into `reports/td2.md`. Nature of the data: **TD 1 values are real traces** (`kit-td1/model-question-comparison-en.csv`, 100 cells); **simulator outputs are synthetic** (no provider call). Twenty questions support a batch-specific hypothesis, not a general error rate, a permanent ranking or a quorum error guarantee.

## 1. Exact TD 1 rates per family (correct / cases)

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

## 2. The one-page rule

Costs of error: **dashboard** (internal, low), **customer figure** (shown outside), **payout** (money moves). "None" is allowed only for a dashboard *and* a family where the chosen model was 100 % in TD 1.

| Family | Cells / rate of the first model | First model (cheapest 100 % free) | Dashboard | Customer figure | Payout | If first model unavailable |
|---|---|---|---|---|---|---|
| F1 period | C01,C04,C05,C06,C07,C20 – 6/6 (all 5 models) | cohere/north-mini-code:free (cost 0; 50 req/day cap) | **none** | 2-of-3 quorum | reference query re-executed + review | next: gpt-oss-20b (Groq free, 6/6), then 120b; can wait → wait for refill |
| F3 product list | C03,C12,C13,C14 – 4/4 (all 5 models) | cohere/north-mini-code:free | **none** | 2-of-3 quorum | reference query + review | same as F1 |
| F2b age at the order | C10 – 1/1 for 120b and 20b (0/1 cohere, qwen, dots) | gpt-oss-20b (Groq free) | 2-of-3 quorum | 3-of-5 quorum + deterministic check | reference query + review | 120b Groq → wait for Groq reset → paid 120b only if budget allows → abstain |
| Combined (C15–C19) | 5/5 for 20b and 120b; 1/5 cohere, 2/5 qwen, 1/5 dots | gpt-oss-20b (Groq free) | 2-of-3 quorum | 3-of-5 quorum + deterministic check | reference query + review | as F2b |
| F2 age on a date | C02,C08,C09,C11 – 4/4 for 120b only (20b 1/4, qwen 3/4) | gpt-oss-120b (Groq free) | **deterministic check** (age-window script / reference SQL) | deterministic check (quorum alone insufficient: C09 shared 0) | reference query + review | wait for Groq refill (can wait) → paid 120b (≈0.00045 $/request) → abstain |

Rules common to all rows: (1) never "none" if the model made ≥1 error on the family (F2, F2b, Comb.) or if the figure goes to a customer or governs a payout; (2) a quorum only counts distinct families and a failed member stays in n (see Step 1); (3) no eligible resource within deadline and budget → **abstain**, never an invented value. Limits: F2b has 1 cell, Combined 5 cells; the 20b "100 %" on Comb./F2b is thin evidence, hence the checks above.

## 3. Simulator outputs

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

## 4. Why `choose` prefers an available included resource to deferring

In `choose` the branches run in this order: (1) `included` = eligible, `available`, `cash == 0`; (2) `waiting` → `defer`; (3) `paid` within budget; (4) abstain. A subscription with `cash == 0` and `allocation > 0` is `available`, so branch 1 returns `run` before branch 2 is even evaluated. The exhausted free resource (`available False`, `allocation == 0`) is only a candidate for branch 2.

Why this priority is sensible:
- **Zero marginal cash, zero delay**: the subscription is already paid, running now spends nothing new and meets any deadline; deferring costs time and the wake-up is only a *recheck* ("reaching a reset time does not prove that capacity is available").
- **Included capacity is perishable**: unused allocation is lost at reset, while a deferral keeps the request pending and can fail on recheck (then paid route or abstain).
- Among included resources the key `(allocation, level, id)` uses the one with least allocation and lowest level first, so small models are used before senior ones.

**When to reverse it** (prefer `defer` to the free resource although the subscription is available): when the request is nonurgent (`can_wait`, `deadline_minutes` clearly larger than `reset_minutes`) **and** the subscription allocation is scarce and must be reserved for requests that need it, i.e. remaining allocation is lower than the expected demand of high-impact / difficulty-3 requests before the next reset (or overage/shared-quota penalties apply), **and** the free resource is itself eligible (level ≥ difficulty, e.g. a TD 1 family where it is 100 %). Reversal is also right when the quorum needs an independent family and the free model provides it. It must **not** be reversed for urgent requests or when the free resource's reset is later than the deadline (the `waiting` filter already excludes it).

Note: in our adapted portfolio there is no subscription resource tested in TD 1 (Claude/Codex/Gemini subscriptions are in the portfolio but have no TD 1 cells), so the priority is exercised on the original simulator (scenarios `complex` vs `deferrable`) and, with the same branch order, on Groq free (included) vs Groq exhausted (defer) vs OpenRouter paid (run) in the adapted one.

## 5. Contribution and limits

- Pair C: rates per family, rule, adapted `RESOURCES`/`choose`, before/after outputs, analysis of `choose`.
- Limits: 20 questions, F2b = 1 cell; prices from `portefeuille-modeles-2026-09-28.csv` / `five-model-summary-en.csv` (OpenRouter list, 2026-10-21); the paid 120b cost is a fictional token envelope; availability is simulated.

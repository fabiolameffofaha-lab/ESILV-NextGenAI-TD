"""TD 2 - Step 2 (Pair B): wrong consensus, SQL root cause, delta query.

Offline only: reads traces-td1.csv, reference-td1.csv, data/boutique.sqlite
(opened read-only) and data/*.csv. No provider call.

    python pair_b_wrong_consensus.py
"""
import csv
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "data" / "boutique.sqlite"

SHORT = {
    "openai/gpt-oss-120b": "120b",
    "openai/gpt-oss-20b": "20b",
    "cohere/north-mini-code:free": "cohere",
    "qwen/qwen3.8-27b": "qwen",
    "dots-studio/dots-3-note-preview:free": "dots",
}
FIXED_PANEL = ["120b", "cohere", "qwen"]          # atelier-vote.py fixed panel
ALL_FIVE = ["120b", "20b", "cohere", "qwen", "dots"]


def connect():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def q(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def section(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


# --------------------------------------------------------------------------
# 1. Last attempt per (question, model) and hand count of the votes
# --------------------------------------------------------------------------
def load_last_attempts():
    rows = list(csv.DictReader(open(HERE / "traces-td1.csv", encoding="utf-8")))
    last = {}
    for r in rows:  # file order = chronological; keep the last attempt
        last[(r["case_id"], SHORT[r["model_requested"]])] = r
    return last


def hand_vote(last, case, panel, k):
    """Same contract as vote_k_sur_n, written independently (Pair B check)."""
    votes = Counter()
    voters = defaultdict(list)
    for m in panel:
        r = last.get((case, m))
        if r and r["verdict"] in ("correct", "incorrect") and r["value"] != "":
            v = int(r["value"])
            votes[v] += 1
            voters[v].append(m)
    if not votes:
        return {"consensus": False, "value": None, "votes": 0, "models": []}
    v, n = votes.most_common(1)[0]
    if n >= k:
        return {"consensus": True, "value": v, "votes": n, "models": voters[v]}
    return {"consensus": False, "value": None, "votes": n, "models": []}


def fmt(d, ref):
    if not d["consensus"]:
        return f"abstain ({d['votes']})"
    ok = "OK" if d["value"] == ref else "WRONG"
    return f"{d['value']} ({d['votes']}) {ok}"


def vote_table(last):
    section("1. Hand count of the votes, last attempt per model (traces-td1.csv)")
    print(f"{'case':5} {'ref':>8} | " + " ".join(f"{m:>8}" for m in ALL_FIVE)
          + " | 2-of-3 fixed panel     | 3-of-5")
    for i in range(1, 21):
        c = f"C{i:02d}"
        ref = int(last[(c, "120b")]["reference"])
        cells = []
        for m in ALL_FIVE:
            r = last[(c, m)]
            cells.append(r["value"] if r["value"] != "" else r["verdict"][:8])
        d3 = hand_vote(last, c, FIXED_PANEL, 2)
        d5 = hand_vote(last, c, ALL_FIVE, 3)
        print(f"{c:5} {ref:>8} | " + " ".join(f"{x:>8}" for x in cells)
              + f" | {fmt(d3, ref):22} | {fmt(d5, ref)}")

    section("Shared wrong values (verdict = incorrect, identical value, >= 2 models)")
    for i in range(1, 21):
        c = f"C{i:02d}"
        wrong = defaultdict(list)
        for m in ALL_FIVE:
            r = last[(c, m)]
            if r["verdict"] == "incorrect":
                wrong[r["value"]].append(m)
        for v, ms in wrong.items():
            if len(ms) >= 2:
                print(f"{c}: value {v} returned by {ms} (reference {last[(c, '120b')]['reference']})")


# --------------------------------------------------------------------------
# 2. C09: replay the queries, isolate the clause, delta query
# --------------------------------------------------------------------------
REF_C09 = """
SELECT COALESCE(SUM(o.quantity_product * p.price), 0)
FROM orders o JOIN product p ON p.product_id = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
WHERE (CAST(strftime('%Y','2026-09-26') AS INT) - CAST(strftime('%Y',c.birth_date) AS INT))
      - (strftime('%m-%d','2026-09-26') < strftime('%m-%d',c.birth_date)) = 25"""

# Predicate of each model, copied from traces-td1.csv (C09), evaluated per customer.
C09_PREDICATES = {
    "cohere": """CAST(SUBSTR(c.birth_date, 1, 4) AS INTEGER) -
        CASE WHEN SUBSTR(c.birth_date, 6, 2) > '09' THEN 1
             WHEN SUBSTR(c.birth_date, 6, 2) = '09' AND SUBSTR(c.birth_date, 9, 2) > '26' THEN 1
             ELSE 0 END = 25""",
    "qwen": """(strftime('%Y', o.date) - strftime('%Y', c.birth_date)) = 25
        AND (strftime('%m-%d', o.date) >= strftime('%m-%d', c.birth_date))
        AND (strftime('%m-%d', o.date) < strftime('%m-%d', date(c.birth_date, '+26 years')))""",
    "dots": """(CAST(substr(c.birth_date, 1, 4) AS INTEGER) + 25 = 2026
        AND substr(c.birth_date, 6, 2) = '09' AND substr(c.birth_date, 9, 2) = '26')
        AND o.date >= '2026-09-26 00:00:00' AND o.date < '2026-09-27 00:00:00'""",
}

# Sub-clauses tested one by one, to find the one that empties the result.
C09_CLAUSES = {
    "cohere": [
        ("birth_year - adj = 25 (no '2026 -')",
         "CAST(SUBSTR(c.birth_date,1,4) AS INTEGER) - CASE WHEN SUBSTR(c.birth_date,6,2) > '09' THEN 1 "
         "WHEN SUBSTR(c.birth_date,6,2)='09' AND SUBSTR(c.birth_date,9,2) > '26' THEN 1 ELSE 0 END = 25"),
        ("same, with 2026 - (fixed)",
         "2026 - CAST(SUBSTR(c.birth_date,1,4) AS INTEGER) - CASE WHEN SUBSTR(c.birth_date,6,2) > '09' THEN 1 "
         "WHEN SUBSTR(c.birth_date,6,2)='09' AND SUBSTR(c.birth_date,9,2) > '26' THEN 1 ELSE 0 END = 25"),
    ],
    "qwen": [
        ("year(o.date) - year(birth) = 25", "(strftime('%Y', o.date) - strftime('%Y', c.birth_date)) = 25"),
        ("md(o.date) >= md(birth)", "strftime('%m-%d', o.date) >= strftime('%m-%d', c.birth_date)"),
        ("md(o.date) < md(birth + 26 years)",
         "strftime('%m-%d', o.date) < strftime('%m-%d', date(c.birth_date, '+26 years'))"),
        ("clauses 2 AND 3 together",
         "strftime('%m-%d', o.date) >= strftime('%m-%d', c.birth_date) AND "
         "strftime('%m-%d', o.date) < strftime('%m-%d', date(c.birth_date, '+26 years'))"),
    ],
    "dots": [
        ("birth_date = 2001-09-26 (single day)",
         "CAST(substr(c.birth_date,1,4) AS INTEGER) + 25 = 2026 AND substr(c.birth_date,6,2)='09' "
         "AND substr(c.birth_date,9,2)='26'"),
        ("order placed on 2026-09-26", "o.date >= '2026-09-26 00:00:00' AND o.date < '2026-09-27 00:00:00'"),
        ("both together", "CAST(substr(c.birth_date,1,4) AS INTEGER) + 25 = 2026 AND substr(c.birth_date,6,2)='09' "
         "AND substr(c.birth_date,9,2)='26' AND o.date >= '2026-09-26 00:00:00' AND o.date < '2026-09-27 00:00:00'"),
    ],
}

BASE = """FROM orders o JOIN product p ON p.product_id = o.product_id
JOIN customers c ON c.customer_id = o.customer_id WHERE """

# Delta query: the rows (customers aged exactly 25 on 2026-09-26) behind the
# gap between the shared value 0 and the reference. Window: born in
# [2000-09-27, 2001-09-26]  <=>  25 <= age < 26 on 2026-09-26.
DELTA_C09 = """
SELECT c.customer_id, c.birth_date,
       COUNT(DISTINCT o.order_id)                      AS n_orders,
       COALESCE(SUM(o.quantity_product * p.price), 0)  AS revenue_cents
FROM customers c
LEFT JOIN orders  o ON o.customer_id = c.customer_id
LEFT JOIN product p ON p.product_id  = o.product_id
WHERE c.birth_date >  date('2026-09-26', '-26 years')   -- > 2000-09-26
  AND c.birth_date <= date('2026-09-26', '-25 years')   -- <= 2001-09-26
GROUP BY c.customer_id, c.birth_date
ORDER BY c.birth_date"""


def c09(con, last):
    section("2. C09 - wrong consensus on 0: replay on data/boutique.sqlite")
    ref = q(con, REF_C09)[0][0]
    print(f"Reference query (reference-td1.csv logic)        -> {ref}")
    for m in ("cohere", "qwen", "dots"):
        sql = last[("C09", m)]["sql"]
        print(f"{m:7} SQL from traces (replayed)                 -> {q(con, sql)[0][0]}")
    for m in ("120b", "20b"):
        print(f"{m:7} SQL from traces (replayed)                 -> {q(con, last[('C09', m)]['sql'])[0][0]}")

    section("3. C09 - isolate the faulty clause (rows of orders x customers kept)")
    total = q(con, "SELECT COUNT(*) " + BASE + "1")[0][0]
    print(f"rows before any filter: {total}")
    for m, clauses in C09_CLAUSES.items():
        print(f"-- {m}")
        for label, pred in clauses:
            n, s = q(con, "SELECT COUNT(*), COALESCE(SUM(o.quantity_product*p.price),0) " + BASE + pred)[0]
            print(f"   {label:42} rows={n:4}  revenue={s}")
    # what does cohere's left-hand side actually compute?
    print("-- cohere: values taken by its 'age' expression")
    for row in q(con, """SELECT MIN(x), MAX(x) FROM (SELECT CAST(SUBSTR(birth_date,1,4) AS INTEGER) -
        CASE WHEN SUBSTR(birth_date,6,2) > '09' THEN 1 WHEN SUBSTR(birth_date,6,2)='09'
        AND SUBSTR(birth_date,9,2) > '26' THEN 1 ELSE 0 END AS x FROM customers)"""):
        print(f"   min={row[0]} max={row[1]}  (a year of birth, never 25)")
    print("-- dots: customers born 2001-09-26 and their orders on 2026-09-26")
    print("  ", q(con, "SELECT customer_id, birth_date FROM customers WHERE birth_date='2001-09-26'"),
          q(con, "SELECT COUNT(*) FROM orders WHERE date >= '2026-09-26' AND date < '2026-09-27'"))

    section("4. C09 - delta query: the rows behind the gap 0 vs reference")
    rows = q(con, DELTA_C09)
    print(f"{'customer':9} {'birth_date':11} {'orders':>6} {'revenue':>9}")
    for r in rows:
        print(f"{r[0]:9} {r[1]:11} {r[2]:>6} {r[3]:>9}")
    s = sum(r[3] for r in rows)
    print(f"sum = {s}  | reference = {ref}  | match = {s == ref}")
    print("Rows kept by cohere / qwen / dots predicates: 0 / 0 / 0 -> whole delta = reference.")

    # Boundary customers: the ones a one-day error would move in or out
    print("-- boundary check (born around 2000-09-26 / 2001-09-26):")
    for r in q(con, """SELECT customer_id, birth_date FROM customers
                       WHERE birth_date BETWEEN '2000-09-24' AND '2000-09-28'
                          OR birth_date BETWEEN '2001-09-24' AND '2001-09-28' ORDER BY birth_date"""):
        print("  ", r)
    return ref


# --------------------------------------------------------------------------
# 3. Independent check: pure Python on the CSV files, no SQL, no model
# --------------------------------------------------------------------------
def age_on(birth: date, d: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


def independent_check(ref):
    section("5. Independent check (Python on data/*.csv, no SQL)")
    price = {r["product_id"]: int(r["price"])
             for r in csv.DictReader(open(HERE / "data/product.csv", encoding="utf-8"))}
    birth = {r["customer_id"]: date.fromisoformat(r["birth_date"])
             for r in csv.DictReader(open(HERE / "data/customers.csv", encoding="utf-8"))}
    d = date(2026, 9, 26)
    total = 0
    for o in csv.DictReader(open(HERE / "data/orders.csv", encoding="utf-8")):
        if age_on(birth[o["customer_id"]], d) == 25:
            total += int(o["quantity_product"]) * price[o["product_id"]]
    print(f"C09 recomputed from CSV = {total} | SQL reference = {ref} | match = {total == ref}")


# --------------------------------------------------------------------------
# 4. Supplied cases: DEMO-SQL-C11 (historical) and DEMO-VOTE (synthetic)
# --------------------------------------------------------------------------
def demo_c11(con):
    section("6. DEMO-SQL-C11 (supplied historical case, Sept. 2026 pilot - NOT our batch)")
    m1 = BASE + "c.birth_date = '2001-12-01'"
    m2 = BASE + ("CAST(strftime('%Y-%m-%d', '2026-12-01') AS TEXT) >= c.birth_date "
                 "AND CAST(strftime('%Y-%m-%d', '2026-12-01', '+1 year') AS TEXT) <= c.birth_date")
    s = "SELECT COALESCE(SUM(o.quantity_product * p.price), 0) "
    print("M1 gpt-oss-20b  (birth_date = '2001-12-01')       ->", q(con, s + m1)[0][0])
    print("M2 cohere       (birth <= 2026-12-01 AND >= 2027-12-01) ->", q(con, s + m2)[0][0])
    print("   customers matching M2 window:",
          q(con, "SELECT COUNT(*) FROM customers c WHERE '2026-12-01' >= c.birth_date "
                 "AND date('2026-12-01','+1 year') <= c.birth_date")[0][0])
    delta = """SELECT c.customer_id, c.birth_date, COALESCE(SUM(o.quantity_product*p.price),0)
        FROM customers c LEFT JOIN orders o ON o.customer_id=c.customer_id
        LEFT JOIN product p ON p.product_id=o.product_id
        WHERE c.birth_date > date('2026-12-01','-26 years') AND c.birth_date <= date('2026-12-01','-25 years')
        GROUP BY c.customer_id ORDER BY c.birth_date"""
    rows = q(con, delta)
    for r in rows:
        print("  ", r)
    ref = [r for r in csv.DictReader(open(HERE / "reference-td1.csv", encoding="utf-8"))
           if r["case_id"] == "C11"][0]
    print(f"delta sum = {sum(r[2] for r in rows)} | reference-td1.csv C11 = {ref['revenue_cents']}")


def demo_vote():
    section("7. DEMO-VOTE (synthetic teaching example, not model output)")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE sales(sale_date TEXT, amount_cents INT)")
    con.execute("INSERT INTO sales VALUES ('2026-01-01', 100)")
    strict = q(con, "SELECT COALESCE(SUM(amount_cents),0) FROM sales "
                    "WHERE sale_date > '2026-01-01' AND sale_date < '2026-01-02'")[0][0]
    incl = q(con, "SELECT COALESCE(SUM(amount_cents),0) FROM sales "
                  "WHERE sale_date >= '2026-01-01' AND sale_date < '2026-01-02'")[0][0]
    print(f"'>' variant (x2) -> {strict} ; '>=' variant (x1) -> {incl} ; reference 100")
    print("2-of-3 vote on [0, 0, 100] -> consensus 0 (WRONG): the shared '>' drops the boundary day.")


def main():
    last = load_last_attempts()
    vote_table(last)
    with connect() as con:
        ref = c09(con, last)
        independent_check(ref)
        demo_c11(con)
    demo_vote()


if __name__ == "__main__":
    main()

import csv
from datetime import date

def load(name):
    with open(f"data/{name}.csv", newline="") as f:
        return list(csv.DictReader(f))

price = {r["product_id"]: int(r["price"]) for r in load("product")}
birth = {r["customer_id"]: date.fromisoformat(r["birth_date"]) for r in load("customers")}
orders = load("orders")

def age(b, ref):
    return ref.year - b.year - ((ref.month, ref.day) < (b.month, b.day))

def revenue(keep):
    return sum(price[o["product_id"]] * int(o["quantity_product"]) for o in orders if keep(o))

def in_period(o, start, end):
    return start <= o["date"] < end

print("C01", revenue(lambda o: in_period(o, "2026-03-01 00:00:00", "2026-06-01 00:00:00")))
print("C02", revenue(lambda o: age(birth[o["customer_id"]], date(2026, 9, 25)) == 25))
print("C03", revenue(lambda o: o["product_id"] in {"a", "b", "c"} and in_period(o, "2026-01-01 00:00:00", "2026-07-01 00:00:00")))
"""Run once to generate demo datasets: python data/gen_datasets.py"""
import random, csv, math
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
DATA = Path(__file__).parent

# ── Retail Sales ─────────────────────────────────────────────────────────────
categories = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books"]
regions    = ["North", "South", "East", "West", "Central"]
segments   = ["Consumer", "Corporate", "Home Office"]
products   = {
    "Electronics": ["Laptop", "Phone", "Tablet", "Headphones", "Monitor"],
    "Clothing":    ["T-Shirt", "Jacket", "Jeans", "Dress", "Shoes"],
    "Home & Garden": ["Chair", "Table", "Lamp", "Rug", "Plant"],
    "Sports":      ["Yoga Mat", "Dumbbell", "Tennis Racket", "Bike Helmet", "Shoes"],
    "Books":       ["Python Guide", "Data Science", "Novel", "Cookbook", "History"],
}
start = date(2023, 1, 1)

rows = []
for i in range(1, 501):
    cat   = random.choice(categories)
    prod  = random.choice(products[cat])
    qty   = random.randint(1, 10)
    price = round(random.uniform(5, 500), 2)
    disc  = round(random.uniform(0, 0.35), 2)
    rev   = round(qty * price * (1 - disc), 2)
    # inject outliers in ~3% of rows
    if random.random() < 0.03:
        rev = round(rev * random.uniform(8, 15), 2)
    rows.append({
        "order_id":         f"ORD-{i:04d}",
        "order_date":       (start + timedelta(days=random.randint(0, 364))).isoformat(),
        "product_category": cat,
        "product_name":     prod,
        "quantity":         qty,
        "unit_price":       price,
        "revenue":          rev,
        "region":           random.choice(regions),
        "customer_segment": random.choice(segments),
        "discount_pct":     disc,
        "returned":         1 if random.random() < 0.12 else 0,
    })
    # inject ~5% nulls in revenue and quantity
    if random.random() < 0.05:
        rows[-1]["revenue"] = ""
    if random.random() < 0.05:
        rows[-1]["quantity"] = ""

with open(DATA / "retail_sales.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# ── IT Service Desk ───────────────────────────────────────────────────────────
priorities  = ["Critical", "High", "Medium", "Low"]
categories2 = ["Network", "Hardware", "Software", "Access", "Email", "Other"]
departments = ["Engineering", "Finance", "HR", "Sales", "Operations", "Marketing"]
teams       = ["Team-A", "Team-B", "Team-C", "Team-D"]

rows2 = []
for i in range(1, 501):
    pri  = random.choices(priorities, weights=[5, 20, 50, 25])[0]
    res  = round(random.uniform(0.5, 72), 1)
    if pri == "Critical": res = round(random.uniform(0.5, 8), 1)
    sla  = 1 if (pri == "Critical" and res > 4) or (pri == "High" and res > 24) else 0
    sat  = round(random.uniform(2.0, 5.0), 1) if sla == 0 else round(random.uniform(1.0, 3.5), 1)
    rows2.append({
        "ticket_id":         f"TKT-{i:04d}",
        "created_date":      (start + timedelta(days=random.randint(0, 364))).isoformat(),
        "priority":          pri,
        "category":          random.choice(categories2),
        "department":        random.choice(departments),
        "resolution_hours":  res,
        "sla_breached":      sla,
        "assigned_team":     random.choice(teams),
        "satisfaction_score": sat,
        "reopen_count":      random.choices([0, 1, 2, 3], weights=[70, 20, 8, 2])[0],
    })
    if random.random() < 0.05:
        rows2[-1]["satisfaction_score"] = ""

with open(DATA / "it_service_desk.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows2[0].keys())
    writer.writeheader()
    writer.writerows(rows2)

print("Generated retail_sales.csv and it_service_desk.csv")

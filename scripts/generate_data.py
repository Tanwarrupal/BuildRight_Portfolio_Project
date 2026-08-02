"""
Generates a realistic synthetic dataset for a fictional building-materials
distributor ("BuildRight Hardware & Materials", Delhi NCR) covering
Jan 2024 - Jun 2026: products, customers, sales transactions, and monthly
inventory. Seasonality is built in (pre-monsoon renovation spike Mar-May,
festive spike Oct-Nov) so forecasting/EDA has real signal to find.
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)

# ---------- Products ----------
categories = {
    "Paints & Finishes": [("Emulsion Paint 20L", 2400, 3200), ("Enamel Paint 4L", 650, 900),
                           ("Primer 10L", 900, 1250), ("Wood Polish 1L", 220, 340)],
    "Tiles & Sanitaryware": [("Ceramic Floor Tile (sqft)", 32, 48), ("Vitrified Tile (sqft)", 55, 82),
                              ("Wash Basin", 1200, 1850), ("Wall-mounted Commode", 4200, 6200)],
    "Plumbing": [("PVC Pipe 4in (10ft)", 420, 600), ("CPVC Pipe 1in (10ft)", 260, 380),
                 ("Bathroom Fitting Set", 1800, 2600), ("Water Tank 1000L", 3800, 5200)],
    "Electricals": [("Copper Wire 90m Coil", 2100, 2900), ("MCB Switch", 180, 260),
                    ("LED Panel Light", 350, 520), ("Ceiling Fan", 1400, 2100)],
    "Hardware & Tools": [("Cement Bag 50kg", 340, 420), ("Steel Rod 12mm (per kg)", 62, 78),
                         ("Hinges Set (10pc)", 150, 230), ("Power Drill Machine", 2200, 3100)],
}

products = []
pid = 1
for cat, items in categories.items():
    for name, cost, price in items:
        products.append({"product_id": f"P{pid:03d}", "product_name": name,
                          "category": cat, "unit_cost": cost, "unit_price": price})
        pid += 1
products_df = pd.DataFrame(products)

# ---------- Customers ----------
cities = ["Gurgaon", "Delhi", "Noida", "Faridabad", "Ghaziabad"]
cust_types = ["Contractor", "Retailer", "Individual Homeowner"]
customers = []
for i in range(1, 41):
    customers.append({
        "customer_id": f"C{i:03d}",
        "customer_type": rng.choice(cust_types, p=[0.45, 0.35, 0.20]),
        "city": rng.choice(cities),
    })
customers_df = pd.DataFrame(customers)

# ---------- Sales transactions ----------
start = date(2024, 1, 1)
end = date(2026, 6, 30)
days = (end - start).days

def seasonal_multiplier(d):
    m = d.month
    mult = 1.0
    if m in (3, 4, 5):          # pre-monsoon renovation season
        mult *= 1.55
    if m in (10, 11):           # festive season
        mult *= 1.35
    if m in (7, 8):             # monsoon slowdown
        mult *= 0.65
    return mult

rows = []
tx_id = 1
for offset in range(days):
    d = start + timedelta(days=offset)
    base_txns = rng.poisson(9 * seasonal_multiplier(d))
    for _ in range(base_txns):
        prod = products_df.sample(1, random_state=rng.integers(0, 1_000_000)).iloc[0]
        cust = customers_df.sample(1, random_state=rng.integers(0, 1_000_000)).iloc[0]
        qty = max(1, int(rng.gamma(2.0, 3.0)))
        discount_pct = round(rng.choice([0, 0, 0, 5, 8, 10, 12]), 1)
        unit_price = prod["unit_price"]
        gross = unit_price * qty
        net = gross * (1 - discount_pct / 100)
        rows.append({
            "transaction_id": f"T{tx_id:06d}",
            "date": d.isoformat(),
            "product_id": prod["product_id"],
            "customer_id": cust["customer_id"],
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "net_revenue": round(net, 2),
            "unit_cost": prod["unit_cost"],
            "total_cost": round(prod["unit_cost"] * qty, 2),
        })
        tx_id += 1

sales_df = pd.DataFrame(rows)

# Inject a few realistic data-quality issues for the "cleaning" story
dirty_idx = rng.choice(sales_df.index, size=int(len(sales_df) * 0.015), replace=False)
sales_df.loc[dirty_idx[: len(dirty_idx)//3], "quantity"] = -1          # bad negative qty
sales_df.loc[dirty_idx[len(dirty_idx)//3: 2*len(dirty_idx)//3], "discount_pct"] = np.nan  # missing discount
dup_rows = sales_df.sample(30, random_state=1)
sales_df = pd.concat([sales_df, dup_rows], ignore_index=True)          # duplicate transactions

# ---------- Monthly inventory ----------
inv_rows = []
months = pd.date_range("2024-01-01", "2026-06-01", freq="MS")
for prod in products_df["product_id"]:
    stock = rng.integers(200, 600)
    for m in months:
        procured = rng.integers(80, 260)
        sold = sales_df[(pd.to_datetime(sales_df["date"]).dt.to_period("M") == m.to_period("M")) &
                         (sales_df["product_id"] == prod)]["quantity"].clip(lower=0).sum()
        closing = max(0, stock + procured - sold)
        inv_rows.append({
            "product_id": prod, "month": m.strftime("%Y-%m"),
            "opening_stock": stock, "procured": procured,
            "sold": int(sold), "closing_stock": closing,
            "reorder_level": 120,
        })
        stock = closing
inventory_df = pd.DataFrame(inv_rows)

# ---------- Save ----------
products_df.to_csv("/home/Rupal/project2/data/products.csv", index=False)
customers_df.to_csv("/home/Rupal/project2/data/customers.csv", index=False)
sales_df.to_csv("/home/Rupal/project2/data/sales_raw.csv", index=False)
inventory_df.to_csv("/home/Rupal/project2/data/inventory.csv", index=False)

print("Products:", len(products_df))
print("Customers:", len(customers_df))
print("Sales rows (with dirty data):", len(sales_df))
print("Inventory rows:", len(inventory_df))

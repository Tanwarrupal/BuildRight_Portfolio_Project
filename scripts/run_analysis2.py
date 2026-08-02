import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

DATA = "/home/Rupal/project2/data"
OUT = "/home/Rupal/project2/outputs"
DB = "/home/Rupal/project2/buildright.db"

conn = sqlite3.connect(DB)
pd.read_csv(f"{DATA}/products.csv").to_sql("products", conn, if_exists="replace", index=False)
pd.read_csv(f"{DATA}/customers.csv").to_sql("customers", conn, if_exists="replace", index=False)
pd.read_csv(f"{DATA}/sales_raw.csv").to_sql("sales_raw", conn, if_exists="replace", index=False)
pd.read_csv(f"{DATA}/inventory.csv").to_sql("inventory", conn, if_exists="replace", index=False)

cur = conn.cursor()

bad_qty = pd.read_sql_query("SELECT COUNT(*) AS bad_quantity_rows FROM sales_raw WHERE quantity <= 0;", conn)
missing_disc = pd.read_sql_query("SELECT COUNT(*) AS missing_discount_rows FROM sales_raw WHERE discount_pct IS NULL;", conn)
dupes = pd.read_sql_query("""
SELECT transaction_id, COUNT(*) AS occurrences FROM sales_raw
GROUP BY transaction_id HAVING COUNT(*) > 1;
""", conn)

cur.execute("DROP TABLE IF EXISTS sales_clean;")
cur.execute("""
CREATE TABLE sales_clean AS
SELECT DISTINCT
    transaction_id, date, product_id, customer_id, quantity, unit_price,
    COALESCE(discount_pct, 0) AS discount_pct,
    net_revenue, unit_cost, total_cost
FROM sales_raw
WHERE quantity > 0;
""")
conn.commit()

revenue_by_category = pd.read_sql_query("""
SELECT p.category,
       ROUND(SUM(s.net_revenue), 0) AS total_revenue,
       ROUND(SUM(s.net_revenue - s.total_cost), 0) AS gross_margin,
       ROUND(100.0 * SUM(s.net_revenue - s.total_cost) / SUM(s.net_revenue), 1) AS margin_pct
FROM sales_clean s JOIN products p ON p.product_id = s.product_id
GROUP BY p.category ORDER BY total_revenue DESC;
""", conn)

monthly_revenue_trend = pd.read_sql_query("""
SELECT strftime('%Y-%m', date) AS month, ROUND(SUM(net_revenue), 0) AS revenue
FROM sales_clean GROUP BY month ORDER BY month;
""", conn)

top10_products = pd.read_sql_query("""
SELECT p.product_name, p.category, SUM(s.quantity) AS units_sold, ROUND(SUM(s.net_revenue), 0) AS revenue
FROM sales_clean s JOIN products p ON p.product_id = s.product_id
GROUP BY p.product_id ORDER BY revenue DESC LIMIT 10;
""", conn)

customer_segment = pd.read_sql_query("""
SELECT c.customer_type, COUNT(DISTINCT s.customer_id) AS num_customers,
       ROUND(SUM(s.net_revenue), 0) AS revenue,
       ROUND(SUM(s.net_revenue) / COUNT(DISTINCT s.customer_id), 0) AS avg_revenue_per_customer
FROM sales_clean s JOIN customers c ON c.customer_id = s.customer_id
GROUP BY c.customer_type ORDER BY revenue DESC;
""", conn)

at_risk_inventory = pd.read_sql_query("""
SELECT i.product_id, p.product_name, p.category, i.month, i.closing_stock, i.reorder_level
FROM inventory i JOIN products p ON p.product_id = i.product_id
WHERE i.closing_stock < i.reorder_level AND i.month = (SELECT MAX(month) FROM inventory)
ORDER BY i.closing_stock ASC;
""", conn)

city_performance = pd.read_sql_query("""
SELECT c.city, ROUND(SUM(s.net_revenue), 0) AS revenue, COUNT(DISTINCT s.transaction_id) AS transactions
FROM sales_clean s JOIN customers c ON c.customer_id = s.customer_id
GROUP BY c.city ORDER BY revenue DESC;
""", conn)

print("Bad qty rows:", bad_qty.iloc[0,0])
print("Missing discount rows:", missing_disc.iloc[0,0])
print("Duplicate transaction ids:", len(dupes))
print("\nRevenue by category:\n", revenue_by_category)
print("\nTop 10 products:\n", top10_products)
print("\nCustomer segment:\n", customer_segment)
print("\nAt-risk inventory (below reorder level, latest month):\n", at_risk_inventory)
print("\nCity performance:\n", city_performance)

revenue_by_category.to_csv(f"{OUT}/revenue_by_category.csv", index=False)
monthly_revenue_trend.to_csv(f"{OUT}/monthly_revenue_trend.csv", index=False)
top10_products.to_csv(f"{OUT}/top10_products.csv", index=False)
customer_segment.to_csv(f"{OUT}/customer_segment.csv", index=False)
at_risk_inventory.to_csv(f"{OUT}/at_risk_inventory.csv", index=False)
city_performance.to_csv(f"{OUT}/city_performance.csv", index=False)

# ---- Forecast: 3-month moving average + linear trend ----
trend = monthly_revenue_trend.copy()
trend["month_dt"] = pd.to_datetime(trend["month"])
trend = trend.sort_values("month_dt").reset_index(drop=True)
trend["moving_avg_3m"] = trend["revenue"].rolling(3).mean()

x = np.arange(len(trend))
coeffs = np.polyfit(x, trend["revenue"], 1)
trend["trend_line"] = np.polyval(coeffs, x)

future_x = np.arange(len(trend), len(trend) + 3)
future_forecast = np.polyval(coeffs, future_x)
last_month = trend["month_dt"].max()
future_months = pd.date_range(last_month + pd.offsets.MonthBegin(1), periods=3, freq="MS")
forecast_df = pd.DataFrame({"month": future_months.strftime("%Y-%m"), "forecast_revenue": future_forecast.round(0)})
forecast_df.to_csv(f"{OUT}/revenue_forecast_next3.csv", index=False)
trend.to_csv(f"{OUT}/monthly_trend_with_ma.csv", index=False)

print("\n3-month forward forecast:\n", forecast_df)

# ---- Charts ----
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.plot(trend["month_dt"], trend["revenue"], marker="o", label="Actual Revenue", color="#1F3864")
ax.plot(trend["month_dt"], trend["moving_avg_3m"], linestyle="--", label="3-Month Moving Avg", color="#C00000")
ax.set_title("Monthly Revenue Trend — BuildRight Hardware & Materials")
ax.set_ylabel("Revenue (₹)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v/100000:.1f}L"))
ax.legend()
fig.autofmt_xdate()
plt.tight_layout()
plt.savefig(f"{OUT}/chart_monthly_revenue_trend.png", dpi=150)
plt.close()

fig, ax = plt.subplots(figsize=(7, 5))
cat = revenue_by_category.sort_values("total_revenue")
ax.barh(cat["category"], cat["total_revenue"], color="#2E5A9C")
ax.set_title("Revenue by Category")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v/100000:.1f}L"))
plt.tight_layout()
plt.savefig(f"{OUT}/chart_revenue_by_category.png", dpi=150)
plt.close()

print("\nDone. Outputs in", OUT)

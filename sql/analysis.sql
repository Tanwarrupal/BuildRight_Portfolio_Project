-- ============================================================
-- BuildRight Hardware & Materials — Sales & Inventory Analysis
-- ============================================================

-- 1. DATA CLEANING: identify bad records before use
-- 1a. Negative/zero quantities (data entry errors)
SELECT COUNT(*) AS bad_quantity_rows FROM sales_raw WHERE quantity <= 0;

-- 1b. Missing discount values
SELECT COUNT(*) AS missing_discount_rows FROM sales_raw WHERE discount_pct IS NULL;

-- 1c. Duplicate transactions (same id appearing more than once)
SELECT transaction_id, COUNT(*) AS occurrences
FROM sales_raw
GROUP BY transaction_id
HAVING COUNT(*) > 1;

-- 1d. Build the CLEAN table: drop bad qty, de-dup, impute discount with 0
DROP TABLE IF EXISTS sales_clean;
CREATE TABLE sales_clean AS
SELECT DISTINCT
    transaction_id, date, product_id, customer_id, quantity, unit_price,
    COALESCE(discount_pct, 0) AS discount_pct,
    net_revenue, unit_cost, total_cost
FROM sales_raw
WHERE quantity > 0;

-- 2. REVENUE BY CATEGORY (joins clean sales to product master)
SELECT p.category,
       ROUND(SUM(s.net_revenue), 0) AS total_revenue,
       ROUND(SUM(s.net_revenue - s.total_cost), 0) AS gross_margin,
       ROUND(100.0 * SUM(s.net_revenue - s.total_cost) / SUM(s.net_revenue), 1) AS margin_pct
FROM sales_clean s
JOIN products p ON p.product_id = s.product_id
GROUP BY p.category
ORDER BY total_revenue DESC;

-- 3. MONTHLY REVENUE TREND (for seasonality / forecasting input)
SELECT strftime('%Y-%m', date) AS month,
       ROUND(SUM(net_revenue), 0) AS revenue
FROM sales_clean
GROUP BY month
ORDER BY month;

-- 4. TOP 10 PRODUCTS BY REVENUE
SELECT p.product_name, p.category,
       SUM(s.quantity) AS units_sold,
       ROUND(SUM(s.net_revenue), 0) AS revenue
FROM sales_clean s
JOIN products p ON p.product_id = s.product_id
GROUP BY p.product_id
ORDER BY revenue DESC
LIMIT 10;

-- 5. CUSTOMER SEGMENT CONTRIBUTION
SELECT c.customer_type,
       COUNT(DISTINCT s.customer_id) AS num_customers,
       ROUND(SUM(s.net_revenue), 0) AS revenue,
       ROUND(SUM(s.net_revenue) / COUNT(DISTINCT s.customer_id), 0) AS avg_revenue_per_customer
FROM sales_clean s
JOIN customers c ON c.customer_id = s.customer_id
GROUP BY c.customer_type
ORDER BY revenue DESC;

-- 6. SLOW-MOVING / AT-RISK INVENTORY (below reorder level at period end)
SELECT i.product_id, p.product_name, p.category, i.month, i.closing_stock, i.reorder_level
FROM inventory i
JOIN products p ON p.product_id = i.product_id
WHERE i.closing_stock < i.reorder_level
  AND i.month = (SELECT MAX(month) FROM inventory)
ORDER BY i.closing_stock ASC;

-- 7. CITY-WISE PERFORMANCE
SELECT c.city,
       ROUND(SUM(s.net_revenue), 0) AS revenue,
       COUNT(DISTINCT s.transaction_id) AS transactions
FROM sales_clean s
JOIN customers c ON c.customer_id = s.customer_id
GROUP BY c.city
ORDER BY revenue DESC;

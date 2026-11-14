-- SYNTHETIC DEMO ONLY. MySQL 8+.
-- Import data/orders.csv and data/invoices_raw.csv into matching MySQL tables.
-- Orders schema: order_id BIGINT PRIMARY KEY, order_date DATE, channel VARCHAR(20),
-- store_id VARCHAR(20), customer_id BIGINT, sku_id VARCHAR(20), quantity INT,
-- unit_price_inr DECIMAL(12,2), net_amount_inr DECIMAL(12,2),
-- item_cost_inr DECIMAL(12,2), order_status VARCHAR(20).
-- Invoice schema: order_id BIGINT, invoice_date DATE, invoice_amount_inr DECIMAL(12,2), invoice_id VARCHAR(40).
-- Don't INNER JOIN first: missing invoices would disappear.

WITH invoice_summary AS (
    SELECT order_id, COUNT(*) AS invoice_count,
           MIN(invoice_amount_inr) AS invoice_amount_inr
    FROM invoices_raw
    GROUP BY order_id
), reconciliation AS (
    SELECT o.order_id, o.channel, o.net_amount_inr,
           i.invoice_count, i.invoice_amount_inr,
           CASE
             WHEN i.order_id IS NULL THEN 'missing_invoice'
             WHEN i.invoice_count > 1 THEN 'duplicate_invoice'
             WHEN ABS(o.net_amount_inr - i.invoice_amount_inr) > 0.01 THEN 'amount_mismatch'
             ELSE 'matched'
           END AS status
    FROM orders o
    LEFT JOIN invoice_summary i ON i.order_id=o.order_id
)
SELECT status, COUNT(*) AS order_count,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM orders),2) AS pct_of_orders
FROM reconciliation
GROUP BY status
ORDER BY order_count DESC;

-- AFTER: change invoices_raw to invoices_after_review in the CTE above;
-- expected synthetic exceptions: 11,250 (1.5%), vs raw 90,000 (12%).

-- Summary business KPIs by channel. These figures are synthetic.
SELECT channel, COUNT(DISTINCT order_id) AS orders,
       SUM(net_amount_inr) AS revenue_inr,
       SUM(net_amount_inr-item_cost_inr) AS product_contribution_inr,
       ROUND(100.0*SUM(net_amount_inr-item_cost_inr)/NULLIF(SUM(net_amount_inr),0),2) AS product_contribution_margin_pct
FROM orders
WHERE order_status='completed'
GROUP BY channel;

-- QA: duplicate invoice IDs, missing order links, source row counts.
SELECT COUNT(*) AS invoices, COUNT(DISTINCT invoice_id) AS distinct_invoice_ids,
       COUNT(DISTINCT order_id) AS covered_order_ids FROM invoices_raw;
SELECT i.order_id FROM invoices_raw i LEFT JOIN orders o ON i.order_id=o.order_id WHERE o.order_id IS NULL LIMIT 20;

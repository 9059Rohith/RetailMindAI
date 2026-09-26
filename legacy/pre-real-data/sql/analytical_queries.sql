USE retailmind;
-- Observed revenue and units by month and region. No forecast values enter this query.
SELECT DATE_FORMAT(s.sale_date, '%Y-%m') AS month, r.region_name,
       SUM(s.units) AS units, SUM(s.units * s.unit_price) AS revenue
FROM sales AS s
JOIN stores AS t ON t.store_id = s.store_id
JOIN regions AS r ON r.region_id = t.region_id
GROUP BY month, r.region_name ORDER BY month, revenue DESC;

-- Latest observed stock for each product/store, without adding historical snapshots.
SELECT i.product_id, i.store_id, i.snapshot_date, i.on_hand
FROM inventory AS i
JOIN (SELECT product_id, store_id, MAX(snapshot_date) AS latest_date
      FROM inventory GROUP BY product_id, store_id) AS recent
  ON recent.product_id = i.product_id AND recent.store_id = i.store_id
 AND recent.latest_date = i.snapshot_date;

-- Product contribution and cumulative ABC input, derived from sales transactions.
WITH product_revenue AS (
  SELECT product_id, SUM(units * unit_price) AS revenue
  FROM sales GROUP BY product_id
)
SELECT product_id, revenue,
       SUM(revenue) OVER (ORDER BY revenue DESC, product_id) /
       NULLIF(SUM(revenue) OVER (), 0) AS cumulative_share
FROM product_revenue ORDER BY revenue DESC;

-- Compare recorded backtest accuracy across registered model runs.
SELECT m.model_name, m.model_version, m.dataset_checksum,
       AVG(f.mae) AS mean_mae, AVG(f.wape) AS mean_wape, AVG(f.bias_units) AS mean_bias
FROM model_runs AS m JOIN forecast_metrics AS f ON f.run_id = m.run_id
GROUP BY m.run_id, m.model_name, m.model_version, m.dataset_checksum
ORDER BY mean_wape;

-- Replenishment queue with traceable explanations.
SELECT r.snapshot_date, p.product_name, s.store_name, r.suggested_order,
       r.risk_level, r.reason
FROM inventory_recommendations AS r
JOIN products AS p ON p.product_id = r.product_id
JOIN stores AS s ON s.store_id = r.store_id
WHERE r.suggested_order > 0
ORDER BY FIELD(r.risk_level, 'Critical', 'High', 'Medium', 'Low'), r.suggested_order DESC;

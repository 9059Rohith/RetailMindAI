# Limitations and next research steps

The bundled dataset is synthetic; its seasonality, discounts and stock events were generated from known rules. It should not be used to claim real-world forecasting accuracy or financial return. Promotion comparisons and log-price association are descriptive, not causal. A real retailer needs order, returns, stock correction and pricing governance before deployment.

Forecast evaluation is series-specific and runs on demand. Sparse intermittent products may require Croston-style methods or probabilistic models. The forecast band is heuristic and uncalibrated. Stock risk is a transparent score, not a fitted stockout probability. EOQ omits supplier minimums, expiry, storage limits and transport. Allocation uses one supply pool and priority weights without equity constraints. The quick database save is designed for demo round trips; a production system needs tenant isolation, authentication, migrations, durable storage and audited model registry.

Future experiments: M5-based external validation, calibrated conformal intervals, hierarchical reconciliation, promotion uplift designs with credible controls, multi-echelon allocation, perishability-aware optimization and drift monitoring.

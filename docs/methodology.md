# Research methodology

## Evidence chain

The application starts with observed M5 sales, calendar and weekly selling-price records. [`scripts/prepare_m5.py`](../scripts/prepare_m5.py) selects five product/store series per store/category using a stable SHA-256 rank that does not depend on demand. The last 731 observed days are converted from the wide M5 format, joined to source calendar/price records, and saved as the bundled sample. Checksums and missing-price count are in [`data/m5_source.json`](../data/m5_source.json).

Data studio checks required IDs, dates and nonnegative sold units; optional fields are reported for availability. Explicit cleaning quarantines invalid rows without filling or capping measurements. Revenue is computed only when price is observed. Profit and inventory planning require additional retailer data and are unavailable for M5.

## Interpretation

| Output | Status | Meaning |
| --- | --- | --- |
| Units, priced revenue and category/store rankings | Observation | Aggregate of selected historical records |
| Holiday comparisons and price association | Description | Associations that may reflect product mix and seasonality |
| Seasonal baseline and Forecast lab result | Prediction | Archival extrapolation from historical sales |
| Held-out residual band | Empirical sensitivity | Historical error spread, without guaranteed future coverage |
| Inventory risk/order quantity | Conditional policy | Requires actual stock, cost, supplier and lead-time records |

Forecast lab compares baseline, statistical and machine-learning models with expanding-window folds. Demand-derived features are shifted to past-only values. The selected model minimizes historical mean WAPE, using MAE to break ties. The forest and gradient boosting estimators have fixed random state 42 for reproducibility. Source prices, future promotions and stock are never used as unknown future inputs.

Run `python -m scripts.evaluate --horizon 14` to write fold metrics under `artifacts/`; run the [full M5 study](m5_validation.md) to reproduce external holdout evidence. These are time-series research results, not causal or financial-impact estimates.

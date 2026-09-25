# Research methodology

## What each output means

| Output | Status | Interpretation |
| --- | --- | --- |
| Sales KPIs and category rankings | Observation | Aggregates of selected historical records |
| Promotion comparison and price association | Statistical association | Confounded by seasonality, product mix and other variables |
| Future demand | Model prediction | Extrapolation evaluated on earlier held-out periods |
| Forecast band | Heuristic uncertainty | MAE-scaled visual range; coverage is not calibrated |
| Risk and reorder quantity | Policy recommendation | Formula result using chosen service level and cost assumptions |
| What-if result | Simulation | Assumed elasticity and promotion uplift, not causal impact |
| Allocation | Optimization | Maximum weighted fulfillment under a single supply constraint |

## Reproducibility

The generator uses NumPy's `default_rng(seed=42)` and a fixed end date (2025-12-31). The committed demo is 12 products × 4 stores × 120 days. The larger generator supports at least 50 products and 10 stores. Forest and gradient boosting models use random state 42. The evaluation command writes actual fold results to `artifacts/model_comparison.csv`; this generated artifact is intentionally not committed.

The data are synthetic, so project outputs prove system behavior and reproducibility, not external validity on a real retailer. There are no real-world ROI claims.

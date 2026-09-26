# External validation on M5

This study uses the public [M5 dataset record from the University of Nicosia](https://doi.org/10.5281/zenodo.10203108). The repository contains **derived metrics only**; it does not redistribute the raw CSV files. The evaluation command verifies the exact sales file with SHA-256 in its output.

## Protocol

1. Read every product/store series in `sales_train_evaluation.csv` and the official `calendar.csv`. The latest 28 days are held out before any model selection.
2. Give every baseline the same preceding 365 days. Evaluate naive, seven-day seasonal naive, and 28-day moving average forecasts across **all** bottom-level product/store series.
3. Select one positive-demand series near the training-demand median from each category/state combination. This selection uses training observations only. On this nine-series sample, run RetailMind's expanding-window model comparison, choose its winner, forecast 28 days, and score against the untouched holdout. Compare with seasonal naive on the same series.
4. Join the sample with the official price and calendar files to measure price availability and event labels. Inventory and unit cost remain unavailable because M5 does not supply them.

The reported measures are WAPE, MAE, RMSE and signed bias. **These are not M5 leaderboard scores:** the official competition uses hierarchical weighted RMSSE. The sample model comparison is deliberately small and cannot establish that a model dominates across all 30,490 series. Retail sales can also be censored by unavailable stock, which M5 cannot resolve.

## Observed results

The 28-day holdout spans **25 April–22 May 2016**. All **30,490** bottom-level series were scored; **812** had zero actual units in this period. Aggregate WAPE uses total absolute error divided by total actual units across all series, so the zero-demand series are included in the error numerator rather than dropped.

| Forecast rule, all series | WAPE | MAE, units/day | RMSE, units/day | Bias, units/day |
| --- | ---: | ---: | ---: | ---: |
| Naive | 95.16% | 1.373 | 2.894 | +0.190 |
| Seven-day seasonal naive | 86.22% | 1.244 | 2.677 | −0.106 |
| 28-day moving average | **73.86%** | **1.066** | **2.243** | −0.056 |

In the nine-series category/state sample, backtest selection beat seasonal naive on the untouched holdout for **3 of 9** series. The median per-series WAPE was **120.82%** for selected models and **128.57%** for seasonal naive. Five selected models were naive, three exponential smoothing, and one moving average; none of the ML candidates won. This is mixed evidence, especially for sparse item/store demand, and argues for intermittent-demand methods and a longer selection horizon before using these forecasts operationally. The nine imported series produced 3,537 product/store/day records with no missing matched prices and 288 event-labeled records.

The exact derived [aggregate metrics](results/m5/summary.json) and [sample results](results/m5/sample_models.csv) are committed for audit. The recorded sales file SHA-256 is `4b4a47c44c38380d2a9168216fea8c9ff2f31b1ddb772f8a0995952a038b8aa0`.

## Reproduce

Download `sales_train_evaluation.csv`, `calendar.csv`, and `sell_prices.csv` from the source record, then run:

```bash
python -m scripts.evaluate_m5 \
  --sales path/to/sales_train_evaluation.csv \
  --calendar path/to/calendar.csv \
  --prices path/to/sell_prices.csv \
  --sample-ml 9 \
  --output-dir artifacts/m5
```

The script writes `summary.json` and `sample_models.csv`. Verified results from this project are archived in [`results/m5`](results/m5).

## Interpretation

The complete series benchmark checks whether simple forecasting rules generalize across the real M5 series. The nine-series experiment tests whether historical backtest selection improves the subsequent 28-day holdout for varied product categories and states. Any difference should be read as evidence for this dataset and split, not a causal or commercial ROI claim.

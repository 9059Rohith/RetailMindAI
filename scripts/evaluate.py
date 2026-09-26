"""Reproducible CLI evaluation of an observed M5 product series."""
import argparse
from pathlib import Path

import pandas as pd

from retailmind.data import enrich
from retailmind.forecast import backtest, daily_series


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/m5_observed.csv.gz")
    parser.add_argument("--product", default=None, help="Observed product ID; defaults to the first in the file")
    parser.add_argument("--horizon", type=int, default=14)
    parser.add_argument("--output", default="artifacts/model_comparison.csv")
    parser.add_argument("--statistical", action="store_true", help="Include ARIMA and SARIMA in the competition")
    args = parser.parse_args()
    data = enrich(pd.read_csv(args.data, low_memory=False))
    product = args.product or str(data.product_id.iloc[0])
    report = backtest(daily_series(data, product), horizon=args.horizon, include_statistical=args.statistical)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(destination, index=False)
    print(report.groupby("model")[["WAPE", "MAE", "Bias"]].mean().sort_values("WAPE").round(2))
    print(f"Saved observed backtest results to {destination}")


if __name__ == "__main__":
    main()

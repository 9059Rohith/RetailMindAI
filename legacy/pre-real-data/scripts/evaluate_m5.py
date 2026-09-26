"""Reproducible external evaluation on the official M5 evaluation file.

The 28 most recent days are held out. Simple baselines are scored across every
product/store series; the app's model-selection workflow is also tested on a
small, stratified category/state sample. Raw M5 files are never committed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd

from retailmind.data import read_m5_sample
from retailmind.forecast import metrics, run_forecast


SOURCE_DOI = "https://doi.org/10.5281/zenodo.10203108"


def _digest(path: Path) -> str:
    checksum = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _score(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    observed = metrics(actual.ravel(), predicted.ravel())
    return {key: round(float(observed[key]), 4) if np.isfinite(observed[key]) else None
            for key in ("WAPE", "MAE", "RMSE", "Bias")}


def evaluate_m5(sales_path: Path, calendar_path: Path, prices_path: Path | None = None,
                horizon: int = 28, history_days: int = 365,
                sample_ml: int = 9) -> tuple[dict, pd.DataFrame]:
    """Score all M5 bottom-level series and a stratified model-selection sample."""
    if min(horizon, history_days) < 1 or sample_ml < 0:
        raise ValueError("Choose a positive horizon/history and nonnegative sample size.")
    columns = pd.read_csv(sales_path, nrows=0).columns.tolist()
    day_columns = sorted((column for column in columns if column.startswith("d_") and column[2:].isdigit()),
                         key=lambda column: int(column[2:]))
    if len(day_columns) < history_days + horizon or history_days < max(42, 3 * min(horizon, 14) + 14):
        raise ValueError("The selected file needs enough training and held-out daily columns.")
    selected_days = day_columns[-(history_days + horizon):]
    identity = [column for column in ("id", "item_id", "cat_id", "store_id", "state_id") if column in columns]
    if not {"item_id", "cat_id", "store_id", "state_id"}.issubset(identity):
        raise ValueError("Expected the official M5 product, category, store and state columns.")
    data = pd.read_csv(sales_path, usecols=identity + selected_days,
                       dtype={column: "int32" for column in selected_days})
    if data.empty or data.duplicated(["item_id", "store_id"]).any():
        raise ValueError("M5 series must have unique product/store keys.")
    calendar = pd.read_csv(calendar_path).set_index("d")
    if not set(selected_days).issubset(calendar.index):
        raise ValueError("Calendar does not cover the selected M5 days.")
    training_days, target_days = selected_days[:-horizon], selected_days[-horizon:]
    train = data[training_days].to_numpy(dtype=float)
    actual = data[target_days].to_numpy(dtype=float)
    predictions = {
        "Naive": np.repeat(train[:, -1:], horizon, axis=1),
        "Seasonal naive": np.tile(train[:, -7:], (1, ceil(horizon / 7)))[:, :horizon],
        "Moving average": np.repeat(train[:, -28:].mean(axis=1, keepdims=True), horizon, axis=1),
    }
    baselines = {name: _score(actual, forecast) for name, forecast in predictions.items()}
    sample_records = []
    if sample_ml:
        data["recent_mean"] = train.mean(axis=1)
        sampled = []
        for _, group in data[data.recent_mean.gt(0)].groupby(["cat_id", "state_id"], sort=True):
            ordered = group.sort_values(["recent_mean", "item_id", "store_id"])
            sampled.append(int(ordered.index[len(ordered) // 2]))
        selected = sampled[:sample_ml]
        dates = pd.to_datetime(calendar.loc[training_days, "date"]).to_numpy()
        for index in selected:
            series = pd.Series(train[index], index=pd.DatetimeIndex(dates))
            result = run_forecast(series, horizon, include_ml=True)
            selected_score = _score(actual[index:index + 1], result.future.forecast.to_numpy()[None, :])
            seasonal_score = _score(actual[index:index + 1], predictions["Seasonal naive"][index:index + 1])
            sample_records.append({"item_id": str(data.at[index, "item_id"]),
                                   "store_id": str(data.at[index, "store_id"]),
                                   "category": str(data.at[index, "cat_id"]),
                                   "state": str(data.at[index, "state_id"]),
                                   "selected_model": result.winner,
                                   "backtest_wape": round(float(result.comparison.iloc[0].WAPE), 4),
                                   "holdout_wape": selected_score["WAPE"],
                                   "holdout_mae": selected_score["MAE"],
                                   "seasonal_naive_wape": seasonal_score["WAPE"]})
    sample = pd.DataFrame(sample_records)
    price_coverage = None
    if prices_path is not None and not sample.empty:
        selected_rows = data.loc[[int(data.index[(data.item_id.eq(row.item_id) & data.store_id.eq(row.store_id))][0])
                                  for row in sample.itertuples()], identity + selected_days]
        sales_bytes = selected_rows.to_csv(index=False).encode("utf-8")
        with calendar_path.open("rb") as calendar_file, prices_path.open("rb") as prices_file:
            imported = read_m5_sample(sales_bytes, calendar_file, prices_file,
                                      max_series=len(selected_rows), max_days=len(selected_days))
        price_coverage = {"rows": len(imported.data), "missing_prices": imported.missing_prices,
                          "holiday_labeled_rows": int(imported.data.holiday.sum()) if "holiday" in imported.data else None}
    summary = {"source": SOURCE_DOI, "sales_sha256": _digest(sales_path),
               "series": len(data), "horizon_days": horizon, "training_days": history_days,
               "holdout_start": str(calendar.loc[target_days[0], "date"]),
               "holdout_end": str(calendar.loc[target_days[-1], "date"]),
               "zero_actual_series": int((actual.sum(axis=1) == 0).sum()),
               "baselines_all_series": baselines, "sample_model_comparisons": len(sample),
               "price_coverage_sample": price_coverage}
    return summary, sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sales", type=Path, required=True, help="Official sales_train_evaluation.csv")
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--history-days", type=int, default=365)
    parser.add_argument("--sample-ml", type=int, default=9)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/m5"))
    args = parser.parse_args()
    summary, sample = evaluate_m5(args.sales, args.calendar, args.prices, args.horizon,
                                  args.history_days, args.sample_ml)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sample.to_csv(args.output_dir / "sample_models.csv", index=False)
    print(json.dumps(summary, indent=2))
    print(f"Saved derived metrics to {args.output_dir}")


if __name__ == "__main__":
    main()

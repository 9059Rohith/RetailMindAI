"""Leakage-safe demand forecasting and rolling-origin model comparison."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from statsmodels.tsa.holtwinters import SimpleExpSmoothing


@dataclass
class ForecastResult:
    history: pd.DataFrame
    future: pd.DataFrame
    comparison: pd.DataFrame
    winner: str
    features: tuple[str, ...]
    trained_at: str


FEATURES = ("dow", "month", "is_weekend", "sin_dow", "cos_dow", "lag_1", "lag_7", "lag_14", "lag_28", "rolling_mean_7", "rolling_mean_28", "rolling_std_7")


def daily_series(data: pd.DataFrame, product_id: str, store_id: str | None = None) -> pd.Series:
    selected = data[data.product_id.eq(product_id)]
    if store_id:
        selected = selected[selected.store_id.eq(store_id)]
    if selected.empty:
        raise ValueError("No history for this product and store.")
    series = selected.groupby("date")["units"].sum().sort_index()
    series.index = pd.to_datetime(series.index)
    return series.asfreq("D", fill_value=0).astype(float)


def make_features(series: pd.Series) -> pd.DataFrame:
    """Every demand-derived feature uses strictly earlier dates."""
    index = pd.to_datetime(series.index)
    prior = series.shift(1)
    frame = pd.DataFrame(index=index)
    frame["dow"] = index.dayofweek
    frame["month"] = index.month
    frame["is_weekend"] = (index.dayofweek >= 5).astype(int)
    frame["sin_dow"] = np.sin(2 * np.pi * index.dayofweek / 7)
    frame["cos_dow"] = np.cos(2 * np.pi * index.dayofweek / 7)
    for lag in (1, 7, 14, 28):
        frame[f"lag_{lag}"] = series.shift(lag).to_numpy()
    frame["rolling_mean_7"] = prior.rolling(7).mean().to_numpy()
    frame["rolling_mean_28"] = prior.rolling(28).mean().to_numpy()
    frame["rolling_std_7"] = prior.rolling(7).std().to_numpy()
    return frame


def metrics(actual: np.ndarray, predicted: np.ndarray, seasonal_scale: float | None = None) -> dict[str, float]:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    err = a - p
    abs_err = np.abs(err)
    denom = np.abs(a).sum()
    nonzero = a != 0
    smape_denom = np.abs(a) + np.abs(p)
    return {"MAE": float(abs_err.mean()), "RMSE": float(np.sqrt(np.mean(err ** 2))),
            "MAPE": float(np.mean(abs_err[nonzero] / np.abs(a[nonzero])) * 100) if nonzero.any() else float("nan"),
            "sMAPE": float(np.mean(np.divide(2 * abs_err, smape_denom, out=np.zeros_like(abs_err), where=smape_denom != 0)) * 100),
            "WAPE": float(abs_err.sum() / denom * 100) if denom else float("nan"),
            "MASE": float(abs_err.mean() / seasonal_scale) if seasonal_scale and seasonal_scale > 0 else float("nan"),
            "R2": float(1 - (err ** 2).sum() / ((a - a.mean()) ** 2).sum()) if len(a) > 1 and ((a - a.mean()) ** 2).sum() else float("nan"),
            "Bias": float((p - a).mean()), "Underforecast": float(np.maximum(a - p, 0).sum()), "Overforecast": float(np.maximum(p - a, 0).sum())}


def _predict_baseline(history: pd.Series, horizon: int, name: str) -> np.ndarray:
    values = history.to_numpy(dtype=float)
    if name == "Seasonal naive":
        return np.resize(values[-7:] if len(values) >= 7 else values[-1:], horizon).clip(0)
    if name == "Moving average":
        return np.repeat(values[-28:].mean(), horizon).clip(0)
    if name == "Exponential smoothing":
        fit = SimpleExpSmoothing(values, initialization_method="estimated").fit(optimized=True)
        return np.asarray(fit.forecast(horizon)).clip(0)
    return np.repeat(values[-1], horizon).clip(0)


def _recursive_ml(history: pd.Series, horizon: int, name: str) -> np.ndarray:
    if len(history) < 70:
        raise ValueError("At least 70 daily observations are required for ML models.")
    features = make_features(history)
    valid = features.notna().all(axis=1)
    if name == "Random forest":
        model = RandomForestRegressor(n_estimators=60, min_samples_leaf=3, random_state=42, n_jobs=-1)
    else:
        model = HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)
    model.fit(features.loc[valid, list(FEATURES)], history.loc[valid])
    extended = history.copy()
    output = []
    for _ in range(horizon):
        tomorrow = extended.index.max() + pd.Timedelta(days=1)
        candidate = pd.concat([extended, pd.Series([np.nan], index=[tomorrow])])
        row = make_features(candidate).iloc[[-1]][list(FEATURES)]
        prediction = max(0.0, float(model.predict(row)[0]))
        output.append(prediction)
        extended.loc[tomorrow] = prediction
    return np.asarray(output)


def predict(history: pd.Series, horizon: int, name: str) -> np.ndarray:
    if name in {"Naive", "Seasonal naive", "Moving average", "Exponential smoothing"}:
        return _predict_baseline(history, horizon, name)
    if name in {"Random forest", "Gradient boosting"}:
        return _recursive_ml(history, horizon, name)
    raise ValueError(f"Unknown model: {name}")


def backtest(series: pd.Series, horizon: int = 14, folds: int = 3, include_ml: bool = True) -> pd.DataFrame:
    """Expanding-window tests: each prediction sees only earlier observations."""
    if len(series) < max(42, horizon * (folds + 2)):
        raise ValueError("More daily history is needed for rolling-origin backtesting.")
    names = ["Naive", "Seasonal naive", "Moving average", "Exponential smoothing"]
    if include_ml and len(series) >= 70 + horizon * folds:
        names += ["Random forest", "Gradient boosting"]
    results = []
    for name in names:
        for fold in range(folds, 0, -1):
            split = len(series) - fold * horizon
            train = series.iloc[:split]
            actual = series.iloc[split:split + horizon].to_numpy()
            try:
                predicted = predict(train, horizon, name)
            except (ValueError, RuntimeError, FloatingPointError):
                continue
            seasonal_scale = float(np.abs(train.diff(7).dropna()).mean()) if len(train) > 7 else None
            results.append({"model": name, "fold": folds - fold + 1, "train_end": str(train.index[-1].date()), **metrics(actual, predicted, seasonal_scale)})
    if not results:
        raise ValueError("No model could be evaluated on this series.")
    return pd.DataFrame(results)


def run_forecast(series: pd.Series, horizon: int = 14, include_ml: bool = True) -> ForecastResult:
    evaluation = backtest(series, min(horizon, 14), include_ml=include_ml)
    summary = evaluation.groupby("model", as_index=False).agg({key: "mean" for key in ("MAE", "RMSE", "MAPE", "sMAPE", "WAPE", "MASE", "R2", "Bias", "Underforecast", "Overforecast")})
    summary = summary.sort_values(["WAPE", "MAE"], na_position="last").reset_index(drop=True)
    winner = str(summary.iloc[0]["model"])
    point = predict(series, horizon, winner)
    residual_scale = max(1.0, float(summary.iloc[0]["MAE"]))
    # Empirical error width, scaled by sqrt(horizon); a heuristic interval, not calibrated coverage.
    steps = np.arange(1, horizon + 1)
    width = 1.645 * residual_scale * np.sqrt(steps / min(horizon, 14))
    future_dates = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
    future = pd.DataFrame({"date": future_dates, "forecast": point, "lower": np.maximum(0, point - width), "upper": point + width})
    history = pd.DataFrame({"date": series.index, "units": series.to_numpy()})
    return ForecastResult(history, future, summary, winner, FEATURES, datetime.now(timezone.utc).isoformat())


def save_artifact(result: ForecastResult, path: str | Path, dataset_version: str) -> Path:
    """Persist forecasts and evaluation metadata without serializing uploaded data."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"future": result.future, "comparison": result.comparison, "winner": result.winner,
                 "features": result.features, "trained_at": result.trained_at, "dataset_version": dataset_version}, target)
    return target


def load_artifact(path: str | Path) -> dict:
    return joblib.load(path)

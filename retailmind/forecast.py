"""Leakage-safe demand forecasting and rolling-origin model comparison."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX


@dataclass
class ForecastResult:
    history: pd.DataFrame
    future: pd.DataFrame
    comparison: pd.DataFrame
    winner: str
    features: tuple[str, ...]
    trained_at: str
    folds: pd.DataFrame
    residuals: pd.DataFrame
    interval_label: str
    coverage_target: float


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
    if name == "ARIMA":
        fit = ARIMA(values, order=(1, 0, 1)).fit()
        return np.asarray(fit.forecast(horizon)).clip(0)
    if name == "SARIMA":
        fit = SARIMAX(values, order=(1, 0, 0), seasonal_order=(1, 0, 0, 7), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=60)
        return np.asarray(fit.forecast(horizon)).clip(0)
    return np.repeat(values[-1], horizon).clip(0)


def _recursive_ml(history: pd.Series, horizon: int, name: str) -> np.ndarray:
    if len(history) < 70:
        raise ValueError("At least 70 daily observations are required for ML models.")
    model = fit_model(history, name)
    extended = history.copy()
    output = []
    for _ in range(horizon):
        tomorrow = extended.index.max() + pd.offsets.Day(1)
        candidate = pd.concat([extended, pd.Series([np.nan], index=[tomorrow])])
        row = make_features(candidate).iloc[[-1]][list(FEATURES)]
        prediction = max(0.0, float(model.predict(row)[0]))
        output.append(prediction)
        extended.loc[tomorrow] = prediction
    return np.asarray(output)


def fit_model(history: pd.Series, name: str):
    """Fit a persistable selected model; baselines retain their recent history as state."""
    values = history.to_numpy(dtype=float)
    if name == "ARIMA":
        return ARIMA(values, order=(1, 0, 1)).fit()
    if name == "SARIMA":
        return SARIMAX(values, order=(1, 0, 0), seasonal_order=(1, 0, 0, 7), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=60)
    if name not in {"Random forest", "Gradient boosting"}:
        return {"name": name, "recent_units": values[-28:].tolist()}
    features = make_features(history)
    valid = features.notna().all(axis=1)
    if name == "Random forest":
        model = RandomForestRegressor(n_estimators=60, min_samples_leaf=3, random_state=42, n_jobs=-1)
    else:
        model = HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)
    model.fit(features.loc[valid, list(FEATURES)], history.loc[valid])
    return model


def predict(history: pd.Series, horizon: int, name: str) -> np.ndarray:
    if name in {"Naive", "Seasonal naive", "Moving average", "Exponential smoothing", "ARIMA", "SARIMA"}:
        return _predict_baseline(history, horizon, name)
    if name in {"Random forest", "Gradient boosting"}:
        return _recursive_ml(history, horizon, name)
    raise ValueError(f"Unknown model: {name}")


def _evaluate(series: pd.Series, horizon: int, folds: int, include_ml: bool,
              include_statistical: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding-window scores and every held-out prediction, made in one pass."""
    if len(series) < max(42, horizon * (folds + 2)):
        raise ValueError("More daily history is needed for rolling-origin backtesting.")
    names = ["Naive", "Seasonal naive", "Moving average", "Exponential smoothing"]
    if include_statistical and len(series) >= 70:
        names += ["ARIMA", "SARIMA"]
    if include_ml and len(series) >= 70 + horizon * folds:
        names += ["Random forest", "Gradient boosting"]
    results = []
    predictions = []
    for name in names:
        for fold in range(folds, 0, -1):
            split = len(series) - fold * horizon
            train = series.iloc[:split]
            actual = series.iloc[split:split + horizon].to_numpy()
            try:
                started = perf_counter()
                predicted = predict(train, horizon, name)
                elapsed = perf_counter() - started
            except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
                continue
            seasonal_scale = float(np.abs(train.diff(7).dropna()).mean()) if len(train) > 7 else None
            fold_number = folds - fold + 1
            results.append({"model": name, "fold": fold_number, "train_end": str(train.index[-1].date()),
                            "horizon": horizon, "fit_predict_seconds": elapsed,
                            **metrics(actual, predicted, seasonal_scale)})
            predictions.extend({"model": name, "fold": fold_number, "step": step,
                                "date": series.index[split + step - 1], "actual": float(observed),
                                "predicted": float(estimated), "residual": float(observed - estimated),
                                "absolute_error": float(abs(observed - estimated))}
                               for step, (observed, estimated) in enumerate(zip(actual, predicted), 1))
    if not results:
        raise ValueError("No model could be evaluated on this series.")
    return pd.DataFrame(results), pd.DataFrame(predictions)


def backtest(series: pd.Series, horizon: int = 14, folds: int = 3, include_ml: bool = True, include_statistical: bool = False) -> pd.DataFrame:
    """Expanding-window tests: each prediction sees only earlier observations."""
    return _evaluate(series, horizon, folds, include_ml, include_statistical)[0]


def run_forecast(series: pd.Series, horizon: int = 14, include_ml: bool = True, include_statistical: bool = False) -> ForecastResult:
    evaluation, residuals = _evaluate(series, min(horizon, 14), 3, include_ml, include_statistical)
    summary = evaluation.groupby("model", as_index=False).agg({key: "mean" for key in ("MAE", "RMSE", "MAPE", "sMAPE", "WAPE", "MASE", "R2", "Bias", "Underforecast", "Overforecast", "fit_predict_seconds")})
    summary = summary.sort_values(["WAPE", "MAE"], na_position="last").reset_index(drop=True)
    winner = str(summary.iloc[0]["model"])
    point = predict(series, horizon, winner)
    chosen_errors = np.sort(residuals.loc[residuals.model.eq(winner), "absolute_error"].to_numpy())
    target_coverage = 0.90
    rank = min(len(chosen_errors), int(np.ceil((len(chosen_errors) + 1) * target_coverage))) - 1
    width = float(chosen_errors[rank])
    future_dates = pd.date_range(series.index.max() + pd.offsets.Day(1), periods=horizon, freq="D")
    future = pd.DataFrame({"date": future_dates, "forecast": point, "lower": np.maximum(0, point - width), "upper": point + width})
    history = pd.DataFrame({"date": series.index, "units": series.to_numpy()})
    label = f"90% target band from {len(chosen_errors)} rolling-origin absolute errors"
    return ForecastResult(history, future, summary, winner, FEATURES, datetime.now(timezone.utc).isoformat(),
                          evaluation, residuals, label, target_coverage)


def explain_model(series: pd.Series, name: str) -> pd.DataFrame:
    """Training-data permutation importance for ML models; association, not causation."""
    if name not in {"Random forest", "Gradient boosting"}:
        return pd.DataFrame(columns=["feature", "importance"])
    features = make_features(series).dropna()
    target = series.loc[features.index]
    model = (RandomForestRegressor(n_estimators=60, min_samples_leaf=3, random_state=42, n_jobs=-1) if name == "Random forest"
             else HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=15, l2_regularization=1.0, random_state=42))
    model.fit(features[list(FEATURES)], target)
    importance = permutation_importance(model, features[list(FEATURES)].tail(28), target.tail(28), n_repeats=3, random_state=42)
    return pd.DataFrame({"feature": FEATURES, "importance": importance.importances_mean}).sort_values("importance", ascending=False).reset_index(drop=True)


def explain_next_day(series: pd.Series, name: str) -> pd.DataFrame:
    """One-at-a-time signed prediction sensitivity versus training medians.

    These changes are neither additive Shapley values nor causal effects.
    """
    if name not in {"Random forest", "Gradient boosting"}:
        return pd.DataFrame(columns=["feature", "signed_change", "direction"])
    model = fit_model(series, name)
    features = make_features(series).dropna()[list(FEATURES)]
    tomorrow = series.index.max() + pd.offsets.Day(1)
    candidate = pd.concat([series, pd.Series([np.nan], index=[tomorrow])])
    row = make_features(candidate).iloc[[-1]][list(FEATURES)]
    baseline = float(model.predict(row)[0])
    records = []
    medians = features.median()
    for feature in FEATURES:
        changed = row.copy()
        changed.loc[tomorrow, feature] = medians[feature]
        delta = baseline - float(model.predict(changed)[0])
        records.append({"feature": feature, "signed_change": delta,
                        "direction": "raises" if delta > 0 else "lowers" if delta < 0 else "neutral"})
    return pd.DataFrame(records).sort_values("signed_change", key=lambda values: values.abs(), ascending=False).reset_index(drop=True)


def save_artifact(result: ForecastResult, path: str | Path, dataset_version: str) -> Path:
    """Persist selected model state, forecasts and evaluation metadata."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    series = pd.Series(result.history.units.to_numpy(dtype=float), index=pd.to_datetime(result.history.date))
    fitted = fit_model(series, result.winner)
    joblib.dump({"future": result.future, "comparison": result.comparison, "folds": result.folds,
                 "residuals": result.residuals, "interval_label": result.interval_label,
                 "coverage_target": result.coverage_target, "winner": result.winner,
                 "features": result.features, "trained_at": result.trained_at, "dataset_version": dataset_version,
                 "model": fitted}, target)
    return target


def load_artifact(path: str | Path) -> dict:
    return joblib.load(path)


def register_artifact(result: ForecastResult, directory: str | Path, dataset_version: str) -> Path:
    """Save a versioned model file with readable metadata for registry browsing."""
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = result.trained_at.replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")
    slug = result.winner.lower().replace(" ", "-")
    path = folder / f"{stamp}-{slug}-{dataset_version[:12]}.joblib"
    save_artifact(result, path, dataset_version)
    row = result.comparison.iloc[0]
    metadata = {"model": result.winner, "trained_at": result.trained_at,
                "dataset_version": dataset_version, "features": list(result.features),
                "horizon": len(result.future), "WAPE": float(row.WAPE), "MAE": float(row.MAE),
                "RMSE": float(row.RMSE), "interval": result.interval_label,
                "artifact": path.name}
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path


def list_artifacts(directory: str | Path) -> pd.DataFrame:
    """List metadata without deserializing model files."""
    folder = Path(directory)
    rows = []
    for path in sorted(folder.glob("*.json"), reverse=True) if folder.exists() else []:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if (folder / row["artifact"]).exists() and Path(row["artifact"]).name == row["artifact"]:
                rows.append(row)
        except (ValueError, KeyError, TypeError):
            continue
    return pd.DataFrame(rows)

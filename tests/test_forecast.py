import numpy as np
import pandas as pd
import pytest

from retailmind.forecast import backtest, load_artifact, make_features, metrics, predict, run_forecast, save_artifact


def series():
    index = pd.date_range("2025-01-01", periods=110)
    return pd.Series(10 + index.dayofweek.to_numpy() * 2 + np.arange(110) * 0.04, index=index)


def test_feature_generation_never_uses_today_or_future():
    original = series()
    changed = original.copy()
    changed.iloc[-1] = 99999
    a = make_features(original)
    b = make_features(changed)
    pd.testing.assert_frame_equal(a, b)
    assert a.iloc[7].lag_7 == original.iloc[0]
    assert a.iloc[7].rolling_mean_7 == pytest.approx(original.iloc[:7].mean())


def test_metrics_are_hand_calculable():
    result = metrics(np.array([10, 20]), np.array([12, 18]), seasonal_scale=2)
    assert result["MAE"] == 2
    assert result["RMSE"] == 2
    assert result["WAPE"] == pytest.approx(13.333333)
    assert result["MASE"] == 1
    assert result["Bias"] == 0


def test_backtest_and_forecast_are_time_aware():
    history = series()
    report = backtest(history, horizon=7, folds=2, include_ml=False)
    assert set(report.fold) == {1, 2}
    assert all(pd.to_datetime(report.train_end) < history.index.max())
    result = run_forecast(history, horizon=7, include_ml=False)
    assert len(result.future) == 7
    assert result.future.date.min() > history.index.max()
    assert (result.future.lower <= result.future.forecast).all()
    assert (result.future.forecast <= result.future.upper).all()
    assert (predict(history, 7, "Seasonal naive") >= 0).all()


def test_statistical_models_return_nonnegative_future_values():
    history = series()
    for name in ("ARIMA", "SARIMA"):
        forecast = predict(history, 3, name)
        assert len(forecast) == 3
        assert np.isfinite(forecast).all()
        assert (forecast >= 0).all()


def test_saved_model_run_has_reproducible_state(tmp_path):
    result = run_forecast(series(), horizon=7, include_ml=False)
    path = save_artifact(result, tmp_path / "run.joblib", "demo-v1")
    loaded = load_artifact(path)
    assert loaded["dataset_version"] == "demo-v1"
    assert loaded["winner"] == result.winner
    assert loaded["model"] is not None
    pd.testing.assert_frame_equal(loaded["future"], result.future)

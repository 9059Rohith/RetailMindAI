import pandas as pd
import pytest

from retailmind.analytics import demand_signals, dimension_summary, holiday_effect, kpis, product_summary
from retailmind.data import enrich


def test_kpis_use_sales_not_snapshot_stock():
    data = enrich(pd.DataFrame({"date": ["2025-01-01", "2025-02-01"], "product_id": ["P1", "P1"], "store_id": ["S1", "S1"],
                                "units": [2, 3], "price": [10, 20], "unit_cost": [5, 10], "stock": [100, 80]}))
    result = kpis(data)
    assert result["revenue"] == 80
    assert result["profit"] == 40
    assert result["units"] == 5
    assert result["margin"] == 50
    assert result["growth"] == pytest.approx(200)
    assert product_summary(data).iloc[0].stock == 80
    store = dimension_summary(data, "store").iloc[0]
    assert store.latest_stock == 80
    assert store.latest_month_growth_pct == pytest.approx(200)


def test_product_summary_aggregates_daily_demand_and_latest_stock_across_stores():
    data = enrich(pd.DataFrame({"date": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"],
                                "product_id": ["P1"] * 4, "store_id": ["S1", "S2", "S1", "S2"],
                                "units": [2, 3, 4, 5], "price": [10] * 4, "stock": [12, 20, 8, 15]}))
    row = product_summary(data).iloc[0]
    assert row.daily_mean == 7
    assert row.stock == 23
    assert row.days_cover == pytest.approx(23 / 7)


def test_demand_anomaly_uses_prior_history_and_dead_stock_needs_observed_age():
    dates = pd.date_range("2025-01-01", periods=45)
    data = enrich(pd.DataFrame({"date": dates, "product_id": "P1", "store_id": "S1",
                                "units": [10] * 44 + [100], "price": 10, "stock": 30}))
    signals, observations = demand_signals(data)
    assert signals["anomalies"] >= 1
    assert bool(observations.iloc[-1].anomaly)
    assert observations.iloc[-1].expected_units == 10
    idle = data.copy()
    idle["units"] = 0
    idle = enrich(idle)
    row = product_summary(idle).iloc[0]
    assert row.dead_stock
    assert row.days_since_sale == 45


def test_holiday_comparison_uses_supplied_labels_and_reports_missing_labels():
    data = enrich(pd.DataFrame({"date": ["2025-01-01", "2025-01-02"], "product_id": ["P1", "P1"],
                                "store_id": ["S1", "S1"], "units": [12, 4], "price": [10, 10],
                                "stock": [20, 16], "holiday": [True, False]}))
    comparison = holiday_effect(data).set_index("holiday")
    assert comparison.loc[True, "mean_units"] == 12
    assert comparison.loc[False, "mean_revenue"] == 40
    assert holiday_effect(data.drop(columns="holiday")).empty

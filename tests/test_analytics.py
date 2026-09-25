import pandas as pd
import pytest

from retailmind.analytics import kpis, product_summary
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


def test_product_summary_aggregates_daily_demand_and_latest_stock_across_stores():
    data = enrich(pd.DataFrame({"date": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"],
                                "product_id": ["P1"] * 4, "store_id": ["S1", "S2", "S1", "S2"],
                                "units": [2, 3, 4, 5], "price": [10] * 4, "stock": [12, 20, 8, 15]}))
    row = product_summary(data).iloc[0]
    assert row.daily_mean == 7
    assert row.stock == 23
    assert row.days_cover == pytest.approx(23 / 7)

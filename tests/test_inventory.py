import pandas as pd
import pytest

from retailmind.data import generate_retail_data
from retailmind.inventory import (abc_xyz, allocate_limited_stock, economic_order_quantity,
                                  plan_replenishment, reorder_point, safety_stock, scenario, stockout_trajectory)
from retailmind.analytics import product_summary


def test_inventory_formulas():
    assert safety_stock(4, 9) == 20
    assert reorder_point(10, 9, 20) == 110
    assert economic_order_quantity(1000, 50, 2) == 224
    with pytest.raises(ValueError):
        economic_order_quantity(1000, 50, 0)


def test_segments_risk_and_replenishment():
    data = generate_retail_data(products=4, stores=2, days=35)
    segments = abc_xyz(product_summary(data))
    assert set(segments.abc).issubset({"A", "B", "C"})
    assert set(segments.xyz).issubset({"X", "Y", "Z"})
    plan = plan_replenishment(data)
    assert len(plan) == 8
    assert (plan.recommended_order >= 0).all()
    assert (plan.reorder_point >= plan.safety_stock).all()
    assert set(plan.risk.astype(str)).issubset({"Low", "Medium", "High", "Critical"})


def test_stockout_simulation_and_scenario():
    path = stockout_trajectory(12, [5, 5, 5])
    assert path.projected_stock.tolist() == [12, 7, 2, 0]
    base = scenario(10, 100, 60, 100, 3, 14)
    promoted = scenario(10, 100, 60, 100, 3, 14, discount_pct=.1, promotion=True, order_qty=200)
    assert promoted["projected_demand"] > base["projected_demand"]
    assert promoted["unmet_demand"] < base["unmet_demand"]


def test_allocation_respects_stock_and_priority():
    requests = pd.DataFrame({"store": ["A", "B"], "demand": [10, 10], "priority": [2, 1]})
    result = allocate_limited_stock(requests, 12)
    assert result.allocated.sum() == 12
    assert result.loc[0, "allocated"] == 10
    assert result.loc[1, "allocated"] == 2

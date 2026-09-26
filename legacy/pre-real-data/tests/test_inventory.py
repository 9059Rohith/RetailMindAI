import pandas as pd
import pytest

from retailmind.data import generate_retail_data
from retailmind.inventory import (RiskSettings, abc_xyz, allocate_limited_stock, economic_order_quantity,
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
    assert segments.strategy.str.len().gt(0).all()
    with pytest.raises(ValueError, match="thresholds"):
        abc_xyz(product_summary(data), abc_a=0.9, abc_b=0.8)
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


def test_dead_stock_is_explained_without_inventing_inventory_age():
    data = generate_retail_data(products=1, stores=1, days=35)
    data["units"] = 0
    data["stock"] = 50
    plan = plan_replenishment(data)
    assert bool(plan.iloc[0].dead_stock)
    assert plan.iloc[0].days_since_sale == 35
    assert plan.iloc[0].reason == "No sales in 30 observed days"


def test_forecast_error_and_policy_change_risk_transparently():
    data = generate_retail_data(products=1, stores=1, days=35)
    data["stock"] = 10_000
    data["stockout"] = False
    policy = RiskSettings(forecast_error_points=25)
    baseline = plan_replenishment(data, risk_settings=policy)
    uncertain = plan_replenishment(data, risk_settings=policy,
                                   forecast_error_rates={("P001", "S01"): 1.0})
    assert uncertain.iloc[0].forecast_error_rate == 1.0
    assert uncertain.iloc[0].risk_score > baseline.iloc[0].risk_score
    with pytest.raises(ValueError, match="Risk settings"):
        plan_replenishment(data, risk_settings=RiskSettings(dead_stock_days=0))

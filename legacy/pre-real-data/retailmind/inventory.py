"""Inventory policy, risk, allocation and scenario calculations."""
from __future__ import annotations

from math import ceil, sqrt
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.stats import norm


@dataclass(frozen=True)
class RiskSettings:
    dead_stock_days: int = 30
    excess_cover_days: int = 60
    volatility_points: int = 8
    stockout_points: int = 10
    forecast_error_points: int = 10


def safety_stock(daily_std: float, lead_time: int, service_level: float = 0.95) -> int:
    if daily_std < 0 or lead_time < 0 or not 0.5 < service_level < 1:
        raise ValueError("Check variability, lead time and service level.")
    return ceil(norm.ppf(service_level) * daily_std * sqrt(lead_time))


def reorder_point(daily_mean: float, lead_time: int, safety: int) -> int:
    if min(daily_mean, lead_time, safety) < 0:
        raise ValueError("Inputs must be nonnegative.")
    return ceil(daily_mean * lead_time + safety)


def economic_order_quantity(annual_demand: float, order_cost: float, annual_holding_cost: float) -> int:
    if annual_demand < 0 or order_cost < 0 or annual_holding_cost <= 0:
        raise ValueError("Demand and ordering cost must be nonnegative; holding cost must be positive.")
    return ceil(sqrt(2 * annual_demand * order_cost / annual_holding_cost))


def abc_xyz(summary: pd.DataFrame, abc_a: float = 0.8, abc_b: float = 0.95,
            xyz_x: float = 0.5, xyz_y: float = 1.0) -> pd.DataFrame:
    if not 0 < abc_a < abc_b < 1 or not 0 < xyz_x < xyz_y:
        raise ValueError("ABC and XYZ thresholds must increase within their valid ranges.")
    data = summary.copy().sort_values("revenue", ascending=False)
    total = data.revenue.sum()
    cumulative_before = data.revenue.cumsum().shift(fill_value=0) / total if total else pd.Series(0, index=data.index)
    data["abc"] = np.select([cumulative_before < abc_a, cumulative_before < abc_b], ["A", "B"], default="C")
    cv = data.demand_cv.fillna(float("inf"))
    data["xyz"] = np.select([cv < xyz_x, cv < xyz_y], ["X", "Y"], default="Z")
    data["segment"] = data.abc + data.xyz
    value_action = {"A": "Review frequently", "B": "Review weekly", "C": "Review periodically"}
    variability_action = {"X": "use lean cover", "Y": "hold moderate buffer", "Z": "hold variability buffer"}
    data["strategy"] = [f"{value_action[a]}; {variability_action[z]}" for a, z in zip(data.abc, data.xyz)]
    return data


def plan_replenishment(data: pd.DataFrame, service_level: float = 0.95, order_cost: float = 350,
                       holding_rate: float = 0.2, risk_settings: RiskSettings | None = None,
                       forecast_error_rates: dict[tuple[str, str], float] | None = None) -> pd.DataFrame:
    """Plan per product/store from observed mean and variability; use latest stock only."""
    if data.empty:
        return pd.DataFrame()
    policy = risk_settings or RiskSettings()
    if policy.dead_stock_days < 1 or policy.excess_cover_days < 1 or min(policy.volatility_points, policy.stockout_points, policy.forecast_error_points) < 0:
        raise ValueError("Risk settings must be positive day thresholds and nonnegative weights.")
    keys = ["product_id", "product", "category", "store_id", "store", "region", "supplier"]
    grouped = data.groupby(keys).agg(daily_mean=("units", "mean"), daily_std=("units", "std"), revenue=("revenue", "sum"),
                                      stockout_rate=("stockout", "mean"), unit_cost=("unit_cost", "mean"), lead_time=("lead_time", "median"))
    latest = data.sort_values("date").groupby(keys)["stock"].last()
    grouped["stock"] = latest
    last_sale = data[data.units.gt(0)].groupby(keys)["date"].max()
    grouped["last_sale_date"] = last_sale
    result = grouped.reset_index()
    observed_days = int((data.date.max() - data.date.min()).days) + 1
    result["days_since_sale"] = (data.date.max() - result.last_sale_date).dt.days.fillna(observed_days).astype(int)
    result["dead_stock"] = result.stock.gt(0) & result.days_since_sale.ge(policy.dead_stock_days)
    result["daily_std"] = result.daily_std.fillna(0)
    result["lead_time"] = result.lead_time.fillna(7).clip(lower=1).round().astype(int)
    result["safety_stock"] = [safety_stock(float(std), int(lead), service_level) for std, lead in zip(result.daily_std, result.lead_time)]
    result["reorder_point"] = [reorder_point(float(mean), int(lead), int(safety)) for mean, lead, safety in zip(result.daily_mean, result.lead_time, result.safety_stock)]
    holding = np.maximum(result.unit_cost.fillna(1).to_numpy() * holding_rate, 0.01)
    result["eoq"] = [economic_order_quantity(float(mean) * 365, order_cost, float(cost)) for mean, cost in zip(result.daily_mean, holding)]
    result["days_cover"] = result.stock / result.daily_mean.replace(0, np.nan)
    result["demand_cv"] = result.daily_std / result.daily_mean.replace(0, np.nan)
    rates = forecast_error_rates or {}
    result["forecast_error_rate"] = [max(0.0, float(rates.get((product, store), 0.0)))
                                     for product, store in zip(result.product_id, result.store_id)]
    result["projected_lead_stock"] = result.stock - result.daily_mean * result.lead_time
    result["shortfall"] = (result.reorder_point - result.stock).clip(lower=0)
    result["recommended_order"] = np.where(result.shortfall > 0, np.maximum(result.shortfall, result.eoq), 0).astype(int)
    severity = np.where(result.stock <= 0, 100, np.where(result.projected_lead_stock < 0, 85, np.where(result.stock < result.reorder_point, 62, np.where(result.dead_stock | result.days_cover.gt(policy.excess_cover_days), 35, 12))))
    adjustment = (result.stockout_rate * policy.stockout_points
                  + result.demand_cv.fillna(0).clip(0, 2) * policy.volatility_points
                  + result.forecast_error_rate.clip(0, 2) * policy.forecast_error_points)
    result["risk_score"] = np.minimum(100, severity + adjustment.round()).astype(int)
    result["risk"] = pd.cut(result.risk_score, bins=[-1, 24, 49, 74, 100], labels=["Low", "Medium", "High", "Critical"])
    result["reason"] = np.select([result.stock.le(0), result.projected_lead_stock.lt(0), result.stock.lt(result.reorder_point), result.dead_stock, result.days_cover.gt(policy.excess_cover_days)],
                                 ["Stock depleted", "Projected demand exceeds stock before delivery", "Below reorder point", f"No sales in {policy.dead_stock_days} observed days", f"Excess cover above {policy.excess_cover_days} days"], default="Within target cover")
    return result.sort_values(["risk_score", "shortfall"], ascending=False).reset_index(drop=True)


def stockout_trajectory(current_stock: int, daily_forecast: np.ndarray, incoming_day: int | None = None, incoming_units: int = 0) -> pd.DataFrame:
    if current_stock < 0 or incoming_units < 0:
        raise ValueError("Stock quantities must be nonnegative.")
    remaining = float(current_stock)
    rows = [(0, remaining)]
    for day, demand in enumerate(daily_forecast, 1):
        if incoming_day == day:
            remaining += incoming_units
        remaining = max(0, remaining - max(0, float(demand)))
        rows.append((day, remaining))
    return pd.DataFrame(rows, columns=["day", "projected_stock"])


def scenario(base_daily_demand: float, price: float, unit_cost: float, stock: int, lead_time: int, horizon: int,
             discount_pct: float = 0, promotion: bool = False, order_qty: int = 0, assumed_elasticity: float = -1.1) -> dict[str, float | str]:
    """Transparent what-if heuristic; uplift and elasticity are assumptions, not causal estimates."""
    if min(base_daily_demand, price, unit_cost, stock, lead_time, horizon, order_qty) < 0 or not 0 <= discount_pct < 1:
        raise ValueError("Scenario inputs must be nonnegative and discount below 100%.")
    effective_price = price * (1 - discount_pct)
    price_factor = (effective_price / price) ** assumed_elasticity if price else 1
    promotion_factor = 1.15 if promotion else 1.0
    demand = base_daily_demand * horizon * price_factor * promotion_factor
    available = stock + order_qty if lead_time <= horizon else stock
    fulfilled = min(demand, available)
    return {"projected_demand": round(demand, 1), "fulfilled_units": round(fulfilled, 1),
            "revenue": round(fulfilled * effective_price, 2), "gross_profit": round(fulfilled * (effective_price - unit_cost), 2),
            "ending_stock": round(max(0, available - fulfilled), 1), "unmet_demand": round(max(0, demand - available), 1),
            "stockout_risk": "High" if demand > available else "Low", "assumed_elasticity": assumed_elasticity}


def allocate_limited_stock(requests: pd.DataFrame, available: int) -> pd.DataFrame:
    """Maximize priority-weighted fulfilled demand under available supply."""
    if available < 0 or not {"store", "demand", "priority"}.issubset(requests):
        raise ValueError("Provide nonnegative available stock and store/demand/priority columns.")
    data = requests.copy()
    if (data[["demand", "priority"]] < 0).any().any():
        raise ValueError("Demand and priority must be nonnegative.")
    if data.empty:
        data["allocated"] = []
        return data
    result = linprog(-data.priority.to_numpy(dtype=float), A_ub=np.ones((1, len(data))), b_ub=[available],
                     bounds=[(0, float(demand)) for demand in data.demand], method="highs")
    if not result.success:
        raise RuntimeError(result.message)
    data["allocated"] = np.floor(result.x).astype(int)
    remainder = min(available - int(data.allocated.sum()), int(data.demand.sum() - data.allocated.sum()))
    for idx in data.sort_values("priority", ascending=False).index:
        if remainder <= 0:
            break
        room = max(0, int(data.loc[idx, "demand"] - data.loc[idx, "allocated"]))
        give = min(room, remainder)
        data.loc[idx, "allocated"] += give
        remainder -= give
    data["unmet"] = data.demand - data.allocated
    return data

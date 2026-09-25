"""Observed-data KPIs and descriptive retail analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes


def kpis(data: pd.DataFrame) -> dict[str, float]:
    if data.empty:
        return {key: 0.0 for key in ("revenue", "units", "profit", "margin", "average_price", "growth", "returns", "stockouts")}
    revenue = float(data["revenue"].sum())
    ordered = data.assign(period=pd.to_datetime(data["date"]).dt.to_period("M"))
    monthly = ordered.groupby("period")["revenue"].sum()
    growth = float((monthly.iloc[-1] / monthly.iloc[-2] - 1) * 100) if len(monthly) > 1 and monthly.iloc[-2] else 0.0
    profit = float(data["profit"].sum(min_count=1))
    return {"revenue": revenue, "units": float(data["units"].sum()), "profit": profit,
            "margin": profit / revenue * 100 if revenue and np.isfinite(profit) else float("nan"),
            "average_price": revenue / data["units"].sum() if data["units"].sum() else 0.0,
            "growth": growth, "returns": float(data["returns"].sum()),
            "stockouts": float(data["stockout"].sum())}


def daily_trend(data: pd.DataFrame) -> pd.DataFrame:
    return data.groupby("date", as_index=False).agg(revenue=("revenue", "sum"), units=("units", "sum"), profit=("profit", "sum"))


def product_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    keys = ["product_id", "product", "category"]
    grouped = data.groupby(keys).agg(units=("units", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum"),
                                      unit_cost=("unit_cost", "mean"), stockouts=("stockout", "mean"))
    daily = data.groupby(keys + ["date"], as_index=False)["units"].sum()
    demand = daily.groupby(keys)["units"].agg(daily_mean="mean", daily_std="std")
    grouped[["daily_mean", "daily_std"]] = demand
    latest_per_store = data.sort_values("date").groupby(keys + ["store_id"], as_index=False)["stock"].last()
    grouped["stock"] = latest_per_store.groupby(keys)["stock"].sum(min_count=1)
    sold = data[data.units.gt(0)].groupby(keys)["date"].max()
    grouped["last_sale_date"] = sold
    observed_days = int((data.date.max() - data.date.min()).days) + 1
    grouped["days_since_sale"] = (data.date.max() - grouped.last_sale_date).dt.days.fillna(observed_days).astype(int)
    grouped["dead_stock"] = grouped.stock.gt(0) & grouped.days_since_sale.ge(30)
    grouped["margin_pct"] = np.where(grouped.revenue > 0, grouped.profit / grouped.revenue * 100, 0)
    grouped["demand_cv"] = grouped.daily_std.fillna(0) / grouped.daily_mean.replace(0, np.nan)
    grouped["days_cover"] = grouped.stock / grouped.daily_mean.replace(0, np.nan)
    grouped["inventory_value"] = grouped.stock * grouped.unit_cost
    grouped["status"] = np.select([grouped.dead_stock, grouped.days_cover.le(7), grouped.days_cover.ge(60), grouped.demand_cv.ge(1)], ["No sales in 30+ days", "Fast mover / low cover", "Excess / slow mover", "Volatile"], default="Healthy")
    grouped.loc[grouped.stock.isna(), "status"] = "Inventory unavailable"
    return grouped.reset_index().sort_values("revenue", ascending=False)


def dimension_summary(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if dimension not in {"category", "store", "region", "product"}:
        raise ValueError("Unsupported dimension")
    grouped = data.groupby(dimension, as_index=False).agg(revenue=("revenue", "sum"), units=("units", "sum"), profit=("profit", "sum"), stockouts=("stockout", "sum"))
    grouped["margin_pct"] = np.where(grouped.revenue > 0, grouped.profit / grouped.revenue * 100, 0)
    latest = data.sort_values("date").groupby(["product_id", "store_id"], as_index=False).tail(1)
    stock = latest.groupby(dimension)["stock"].sum(min_count=1)
    grouped["latest_stock"] = grouped[dimension].map(stock)
    monthly = data.assign(month=data.date.dt.to_period("M")).groupby([dimension, "month"])["revenue"].sum().unstack(fill_value=0)
    if len(monthly.columns) >= 2:
        previous, current = monthly.iloc[:, -2], monthly.iloc[:, -1]
        growth = (current / previous.replace(0, np.nan) - 1) * 100
        grouped["latest_month_growth_pct"] = grouped[dimension].map(growth)
    else:
        grouped["latest_month_growth_pct"] = np.nan
    return grouped.sort_values("revenue", ascending=False)


def promotion_effect(data: pd.DataFrame) -> pd.DataFrame:
    result = data.groupby("promotion", as_index=False).agg(mean_units=("units", "mean"), mean_revenue=("revenue", "mean"), observations=("units", "size"))
    return result


def weekday_pattern(data: pd.DataFrame) -> pd.DataFrame:
    result = data.assign(weekday=pd.to_datetime(data["date"]).dt.day_name()).groupby("weekday", as_index=False).agg(mean_units=("units", "mean"))
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result["weekday"] = pd.Categorical(result.weekday, categories=order, ordered=True)
    return result.sort_values("weekday")


def demand_signals(data: pd.DataFrame) -> tuple[dict[str, float | int | None], pd.DataFrame]:
    """Descriptive trend/seasonality and past-only robust daily anomaly flags."""
    trend = daily_trend(data).sort_values("date")
    if trend.empty:
        return {"trend_28d_pct": None, "weekly_strength": None, "monthly_strength": None,
                "yearly_strength": None, "volatility_cv": None, "anomalies": 0}, trend
    values = trend.units.astype(float)
    recent = values.tail(28).to_numpy()
    slope = float(theilslopes(recent, np.arange(len(recent))).slope) if len(recent) >= 7 else 0.0
    mean = float(np.mean(recent))
    trend_pct = slope * 28 / mean * 100 if mean else 0.0
    dates = pd.to_datetime(trend.date)
    overall = float(values.mean())
    def strength(groups: pd.Series) -> float | None:
        if not overall or groups.nunique() < 2:
            return None
        return float(values.groupby(groups).mean().std(ddof=0) / overall)
    weekly = strength(dates.dt.dayofweek)
    monthly = strength(dates.dt.month) if len(trend) >= 60 else None
    yearly = strength(dates.dt.month) if (dates.max() - dates.min()).days >= 730 else None
    history = values.shift(1)
    baseline = history.rolling(28, min_periods=14).median()
    deviation = (history - baseline).abs().rolling(28, min_periods=14).median()
    scale = (1.4826 * deviation).where(deviation.gt(0), 1.0)
    trend["expected_units"] = baseline
    trend["anomaly_score"] = ((values - baseline) / scale).replace([np.inf, -np.inf], np.nan)
    trend["anomaly"] = trend.anomaly_score.abs().ge(3.5) & baseline.notna()
    summary = {"trend_28d_pct": trend_pct, "weekly_strength": weekly,
               "monthly_strength": monthly, "yearly_strength": yearly,
               "volatility_cv": float(values.std(ddof=0) / overall) if overall else 0.0,
               "anomalies": int(trend.anomaly.sum())}
    return summary, trend


def approximate_price_relationship(data: pd.DataFrame) -> dict[str, float | str]:
    """Descriptive elasticity estimate; observations do not establish causality."""
    daily = data.groupby(["date", "product_id"], as_index=False).agg(units=("units", "sum"), price=("price", "mean"))
    daily = daily[(daily.units > 0) & (daily.price > 0)]
    if len(daily) < 20 or daily.price.nunique() < 3:
        return {"elasticity": float("nan"), "note": "Insufficient price variation"}
    x = np.log(daily.price.to_numpy())
    y = np.log(daily.units.to_numpy())
    return {"elasticity": float(np.polyfit(x, y, 1)[0]), "correlation": float(np.corrcoef(x, y)[0, 1]),
            "note": "Observational association; promotions and seasonality may confound it"}

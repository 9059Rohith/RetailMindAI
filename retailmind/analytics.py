"""Observed-data KPIs and descriptive retail analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd


def kpis(data: pd.DataFrame) -> dict[str, float]:
    if data.empty:
        return {key: 0.0 for key in ("revenue", "units", "profit", "margin", "average_price", "growth", "returns", "stockouts")}
    revenue = float(data["revenue"].sum())
    ordered = data.assign(period=pd.to_datetime(data["date"]).dt.to_period("M"))
    monthly = ordered.groupby("period")["revenue"].sum()
    growth = float((monthly.iloc[-1] / monthly.iloc[-2] - 1) * 100) if len(monthly) > 1 and monthly.iloc[-2] else 0.0
    profit = float(data["profit"].sum())
    return {"revenue": revenue, "units": float(data["units"].sum()), "profit": profit,
            "margin": profit / revenue * 100 if revenue else 0.0,
            "average_price": revenue / data["units"].sum() if data["units"].sum() else 0.0,
            "growth": growth, "returns": float(data["returns"].sum()),
            "stockouts": float(data["stockout"].sum())}


def daily_trend(data: pd.DataFrame) -> pd.DataFrame:
    return data.groupby("date", as_index=False).agg(revenue=("revenue", "sum"), units=("units", "sum"), profit=("profit", "sum"))


def product_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    keys = ["product_id", "product", "category"]
    grouped = data.groupby(keys).agg(units=("units", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum"), stockouts=("stockout", "mean"))
    daily = data.groupby(keys + ["date"], as_index=False)["units"].sum()
    demand = daily.groupby(keys)["units"].agg(daily_mean="mean", daily_std="std")
    grouped[["daily_mean", "daily_std"]] = demand
    latest_per_store = data.sort_values("date").groupby(keys + ["store_id"], as_index=False)["stock"].last()
    grouped["stock"] = latest_per_store.groupby(keys)["stock"].sum()
    grouped["margin_pct"] = np.where(grouped.revenue > 0, grouped.profit / grouped.revenue * 100, 0)
    grouped["demand_cv"] = grouped.daily_std.fillna(0) / grouped.daily_mean.replace(0, np.nan)
    grouped["days_cover"] = grouped.stock / grouped.daily_mean.replace(0, np.nan)
    grouped["status"] = np.select([grouped.days_cover.le(7), grouped.days_cover.ge(60), grouped.demand_cv.ge(1)], ["Fast mover / low cover", "Excess / slow mover", "Volatile"], default="Healthy")
    return grouped.reset_index().sort_values("revenue", ascending=False)


def dimension_summary(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if dimension not in {"category", "store", "region", "product"}:
        raise ValueError("Unsupported dimension")
    grouped = data.groupby(dimension, as_index=False).agg(revenue=("revenue", "sum"), units=("units", "sum"), profit=("profit", "sum"), stockouts=("stockout", "sum"))
    grouped["margin_pct"] = np.where(grouped.revenue > 0, grouped.profit / grouped.revenue * 100, 0)
    return grouped.sort_values("revenue", ascending=False)


def promotion_effect(data: pd.DataFrame) -> pd.DataFrame:
    result = data.groupby("promotion", as_index=False).agg(mean_units=("units", "mean"), mean_revenue=("revenue", "mean"), observations=("units", "size"))
    return result


def weekday_pattern(data: pd.DataFrame) -> pd.DataFrame:
    result = data.assign(weekday=pd.to_datetime(data["date"]).dt.day_name()).groupby("weekday", as_index=False).agg(mean_units=("units", "mean"))
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result["weekday"] = pd.Categorical(result.weekday, categories=order, ordered=True)
    return result.sort_values("weekday")


def approximate_price_relationship(data: pd.DataFrame) -> dict[str, float | str]:
    """Descriptive elasticity estimate; observations do not establish causality."""
    daily = data.groupby(["date", "product_id"], as_index=False).agg(units=("units", "sum"), price=("price", "mean"))
    daily = daily[(daily.units > 0) & (daily.price > 0)]
    if len(daily) < 20 or daily.price.nunique() < 3:
        return {"elasticity": float("nan"), "note": "Insufficient price variation"}
    x = np.log(daily.price.to_numpy())
    y = np.log(daily.units.to_numpy())
    return {"elasticity": float(np.polyfit(x, y, 1)[0]), "note": "Observational association; promotions and seasonality may confound it"}

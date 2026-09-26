"""Traceable, rule-based business insights and alerts."""
from __future__ import annotations

import pandas as pd

from .analytics import demand_signals
from .inventory import RiskSettings


def build_insights(data: pd.DataFrame, plan: pd.DataFrame,
                   risk_settings: RiskSettings | None = None) -> list[dict[str, str]]:
    policy = risk_settings or RiskSettings()
    results = []
    daily = data.groupby("date")["units"].sum().sort_index()
    if len(daily) >= 56 and daily.iloc[-56:-28].sum() > 0:
        recent = float(daily.iloc[-28:].sum())
        previous = float(daily.iloc[-56:-28].sum())
        change = (recent / previous - 1) * 100
        results.append({"level": "Opportunity" if change >= 5 else "Warning" if change <= -5 else "Info",
                        "title": "Observed demand rose" if change >= 5 else "Observed demand softened" if change <= -5 else "28-day demand comparison",
                        "detail": f"{recent:,.0f} units in the latest 28 observed days versus {previous:,.0f} in the preceding 28 days ({change:+.1f}%).",
                        "basis": "Observed unit sales · equal 28-day windows"})
    if "category" in data and data.units.sum() > 0:
        categories = data.groupby("category", dropna=True).units.sum().sort_values(ascending=False)
        if not categories.empty:
            leader = categories.iloc[0]
            results.append({"level": "Info", "title": f"{categories.index[0]} leads unit sales",
                            "detail": f"{leader:,.0f} observed units, {leader / data.units.sum() * 100:.1f}% of units in the selected records.",
                            "basis": "Observed unit sales · category mix"})
    if "price" in data and data.price.isna().any():
        missing_prices = int(data.price.isna().sum())
        results.append({"level": "Info", "title": "Revenue has incomplete price coverage",
                        "detail": f"{missing_prices:,} of {len(data):,} selected records have no observed selling price; their units count toward demand, but not revenue.",
                        "basis": "Observed selling-price availability"})
    signals, observations = demand_signals(data)
    recent_anomalies = observations.tail(14).loc[lambda frame: frame.anomaly] if "anomaly" in observations else observations
    if not recent_anomalies.empty:
        latest = recent_anomalies.iloc[-1]
        results.append({"level": "Warning", "title": "Unusual recent demand",
                        "detail": f"{latest.date:%d %b %Y}: {latest.units:,.0f} units versus a prior rolling median of {latest.expected_units:,.0f}. Investigate before changing a forecast.",
                        "basis": "Observed sales · robust anomaly rule"})
    if not plan.empty:
        urgent = plan[plan.risk.isin(["High", "Critical"])]
        results.append({"level": "Critical" if plan.risk.eq("Critical").any() else "Info", "title": f"{len(urgent):,} product-store pairs need attention", "detail": "Review the replenishment list, starting with projected lead-time shortfalls.", "basis": "Inventory policy"})
        excess = plan[plan.days_cover.gt(policy.excess_cover_days)]
        if len(excess):
            results.append({"level": "Warning", "title": f"{len(excess):,} pairs have over {policy.excess_cover_days} days of cover", "detail": "Consider rebalancing inventory after checking shelf life and transfer cost.", "basis": "Inventory policy"})
        idle = plan[plan.dead_stock]
        if len(idle):
            results.append({"level": "Warning", "title": f"{len(idle):,} stocked pairs had no sales for {policy.dead_stock_days}+ observed days",
                            "detail": "The measure is days since a recorded sale, not the physical age of each unit. Review demand, expiry and transfer options.",
                            "basis": "Observed sales + latest stock"})
        for _, row in urgent.head(5).iterrows():
            results.append({"level": "Critical" if row.risk == "Critical" else "Warning", "title": f"{row['product']} · {row['store']}", "detail": f"{row['reason']}. Recommend {int(row['recommended_order']):,} units; latest stock {int(row['stock']):,}.", "basis": "Observed stock + statistical demand"})
    elif any(col not in data or data[col].isna().all() for col in ("stock", "unit_cost", "lead_time")):
        results.append({"level": "Info", "title": "Inventory actions are unavailable",
                        "detail": "Observed stock, unit cost and lead time are required before a reorder or profit recommendation can be calculated.",
                        "basis": "Source field availability"})
    return results

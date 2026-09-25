"""Traceable, rule-based business insights and alerts."""
from __future__ import annotations

import pandas as pd

from .analytics import demand_signals, kpis
from .inventory import RiskSettings


def build_insights(data: pd.DataFrame, plan: pd.DataFrame,
                   risk_settings: RiskSettings | None = None) -> list[dict[str, str]]:
    policy = risk_settings or RiskSettings()
    results = []
    indicators = kpis(data)
    if indicators["growth"] > 5:
        results.append({"level": "Opportunity", "title": "Revenue is growing", "detail": f"Latest monthly revenue is {indicators['growth']:.1f}% above the preceding month in the selected data.", "basis": "Observed sales"})
    elif indicators["growth"] < -5:
        results.append({"level": "Warning", "title": "Revenue has softened", "detail": f"Latest monthly revenue is {abs(indicators['growth']):.1f}% below the preceding month.", "basis": "Observed sales"})
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
    return results

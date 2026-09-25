"""Traceable, rule-based business insights and alerts."""
from __future__ import annotations

import pandas as pd

from .analytics import kpis


def build_insights(data: pd.DataFrame, plan: pd.DataFrame) -> list[dict[str, str]]:
    results = []
    indicators = kpis(data)
    if indicators["growth"] > 5:
        results.append({"level": "Opportunity", "title": "Revenue is growing", "detail": f"Latest monthly revenue is {indicators['growth']:.1f}% above the preceding month in the selected data.", "basis": "Observed sales"})
    elif indicators["growth"] < -5:
        results.append({"level": "Watch", "title": "Revenue has softened", "detail": f"Latest monthly revenue is {abs(indicators['growth']):.1f}% below the preceding month.", "basis": "Observed sales"})
    if not plan.empty:
        urgent = plan[plan.risk.isin(["High", "Critical"])]
        results.append({"level": "Action", "title": f"{len(urgent):,} product-store pairs need attention", "detail": "Review the replenishment list, starting with projected lead-time shortfalls.", "basis": "Inventory policy"})
        excess = plan[plan.days_cover.gt(60)]
        if len(excess):
            results.append({"level": "Watch", "title": f"{len(excess):,} pairs have over 60 days of cover", "detail": "Consider rebalancing inventory after checking shelf life and transfer cost.", "basis": "Inventory policy"})
        for _, row in urgent.head(5).iterrows():
            results.append({"level": "Alert", "title": f"{row['product']} · {row['store']}", "detail": f"{row['reason']}. Recommend {int(row['recommended_order']):,} units; latest stock {int(row['stock']):,}.", "basis": "Observed stock + statistical demand"})
    return results

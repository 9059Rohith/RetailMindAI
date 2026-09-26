"""Isolated deterministic records for formula and persistence tests only."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from retailmind.data import enrich

CATEGORIES = ("Grocery", "Apparel", "Electronics", "Home", "Beauty", "Sports")
REGIONS = ("North", "South", "East", "West")
PRODUCT_NAMES = ("Daily essentials", "Signature blend", "Core collection", "Premium kit", "Everyday line", "Seasonal edit", "Active series", "Classic range", "Fresh pick", "Studio edition")


@dataclass(frozen=True)
class SyntheticConfig:
    regions: int = 4
    categories: int = 6
    end_date: str = "2025-12-31"
    seasonality_strength: float = 0.18
    promotion_frequency: float = 0.09
    price_variation: float = 0.0
    stockout_probability: float = 0.0
    lead_time_low: int = 3
    lead_time_high: int = 14
    demand_volatility: float = 1.0
    yearly_strength: float = 0.0
    slow_mover_share: float = 0.0


def generate_retail_data(products: int = 54, stores: int = 12, days: int = 180, seed: int = 42,
                         config: SyntheticConfig | None = None) -> pd.DataFrame:
    """Generate deterministic daily sales with promotion, seasonality and inventory variation."""
    settings = config or SyntheticConfig()
    if min(products, stores, days) < 1 or not 1 <= settings.regions <= len(REGIONS) or not 1 <= settings.categories <= len(CATEGORIES):
        raise ValueError("Choose positive dimensions and supported region/category counts.")
    if not 0 <= settings.promotion_frequency <= 1 or not 0 <= settings.stockout_probability <= 1 or not 0 <= settings.slow_mover_share <= 1:
        raise ValueError("Frequencies must be between 0 and 1.")
    if settings.lead_time_low < 1 or settings.lead_time_high < settings.lead_time_low or settings.demand_volatility < 1:
        raise ValueError("Check lead-time range and demand volatility.")
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(settings.end_date)
    dates = pd.date_range(end=end, periods=days, freq="D")
    records = []
    for p in range(products):
        category = CATEGORIES[p % settings.categories]
        base_price = round(float(rng.uniform(80, 2400)), 2)
        base_demand = float(rng.uniform(3, 24))
        if settings.slow_mover_share and rng.random() < settings.slow_mover_share:
            base_demand *= 0.15
        cost_ratio = float(rng.uniform(0.5, 0.82))
        for s in range(stores):
            region = REGIONS[s % settings.regions]
            store_factor = float(rng.uniform(0.65, 1.4))
            lead_time = int(rng.integers(settings.lead_time_low, settings.lead_time_high + 1))
            supplier = f"SUP-{p % 9 + 1:02d}"
            stock = int(base_demand * store_factor * rng.uniform(5, 22))
            supply_factor = float(rng.uniform(0.9, 1.4))
            for i, date in enumerate(dates):
                promotion = bool(rng.random() < settings.promotion_frequency)
                discount = float(rng.choice([0.05, 0.10, 0.15, 0.20])) if promotion else 0.0
                holiday = bool((date.month, date.day) in {(1, 1), (8, 15), (10, 2), (12, 25)})
                seasonal = 1 + settings.seasonality_strength * np.sin(2 * np.pi * (i + p * 4) / 30)
                seasonal += settings.yearly_strength * np.sin(2 * np.pi * i / 365)
                weekend = 1.16 if date.dayofweek >= 5 else 1.0
                trend = 1 + i / max(days, 1) * (0.12 if p % 3 else -0.08)
                mean = max(0.1, base_demand * store_factor * seasonal * weekend * trend * (1.28 if promotion else 1) * (1.25 if holiday else 1))
                if settings.demand_volatility > 1:
                    spread = np.log(settings.demand_volatility)
                    mean *= float(rng.lognormal(-0.5 * spread * spread, spread))
                requested = int(rng.poisson(mean))
                disruption = settings.stockout_probability and rng.random() < settings.stockout_probability
                if i and i % lead_time == 0 and not disruption:
                    stock += int(base_demand * store_factor * lead_time * supply_factor * rng.uniform(0.9, 1.1))
                sold = min(requested, stock)
                stock -= sold
                returns = int(rng.binomial(sold, 0.015))
                price_factor = max(0.1, 1 + rng.normal(0, settings.price_variation)) if settings.price_variation else 1
                unit_price = round(base_price * (1 - discount) * price_factor, 2)
                records.append((date, f"P{p+1:03d}", f"{PRODUCT_NAMES[p % len(PRODUCT_NAMES)]} {p+1:02d}", category, f"S{s+1:02d}", f"Store {s+1:02d}", region, sold, unit_price, discount, promotion, holiday, "Rain" if rng.random() < 0.12 else "Clear", stock, supplier, lead_time, returns, round(base_price * cost_ratio, 2), requested > sold))
    frame = pd.DataFrame.from_records(records, columns=["date", "product_id", "product", "category", "store_id", "store", "region", "units", "price", "discount", "promotion", "holiday", "weather", "stock", "supplier", "lead_time", "returns", "unit_cost", "stockout"])
    return enrich(frame)

"""Synthetic data, ingestion, validation, and explicit cleaning."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pandas as pd

REQUIRED = {"date", "product_id", "store_id", "units", "price", "stock"}
CATEGORIES = ("Grocery", "Apparel", "Electronics", "Home", "Beauty", "Sports")
REGIONS = ("North", "South", "East", "West")
PRODUCT_NAMES = ("Daily essentials", "Signature blend", "Core collection", "Premium kit", "Everyday line", "Seasonal edit", "Active series", "Classic range", "Fresh pick", "Studio edition")


@dataclass(frozen=True)
class QualityReport:
    rows: int
    columns: int
    missing_pct: float
    duplicates: int
    invalid_dates: int
    negative_units: int
    negative_stock: int
    outliers: int
    missing_ids: int
    score: int
    issues: tuple[str, ...]


def generate_retail_data(products: int = 54, stores: int = 12, days: int = 180, seed: int = 42) -> pd.DataFrame:
    """Generate deterministic daily sales with promotion, seasonality and inventory variation."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp("2025-12-31")
    dates = pd.date_range(end=end, periods=days, freq="D")
    records = []
    for p in range(products):
        category = CATEGORIES[p % len(CATEGORIES)]
        base_price = round(float(rng.uniform(80, 2400)), 2)
        base_demand = float(rng.uniform(3, 24))
        cost_ratio = float(rng.uniform(0.5, 0.82))
        for s in range(stores):
            region = REGIONS[s % len(REGIONS)]
            store_factor = float(rng.uniform(0.65, 1.4))
            lead_time = int(rng.integers(3, 15))
            supplier = f"SUP-{p % 9 + 1:02d}"
            stock = int(base_demand * store_factor * rng.uniform(5, 22))
            supply_factor = float(rng.uniform(0.9, 1.4))
            for i, date in enumerate(dates):
                promotion = bool(rng.random() < 0.09)
                discount = float(rng.choice([0.05, 0.10, 0.15, 0.20])) if promotion else 0.0
                holiday = bool((date.month, date.day) in {(1, 1), (8, 15), (10, 2), (12, 25)})
                seasonal = 1 + 0.18 * np.sin(2 * np.pi * (i + p * 4) / 30)
                weekend = 1.16 if date.dayofweek >= 5 else 1.0
                trend = 1 + i / max(days, 1) * (0.12 if p % 3 else -0.08)
                mean = max(0.1, base_demand * store_factor * seasonal * weekend * trend * (1.28 if promotion else 1) * (1.25 if holiday else 1))
                requested = int(rng.poisson(mean))
                if i and i % lead_time == 0:
                    stock += int(base_demand * store_factor * lead_time * supply_factor * rng.uniform(0.9, 1.1))
                sold = min(requested, stock)
                stock -= sold
                returns = int(rng.binomial(sold, 0.015))
                unit_price = round(base_price * (1 - discount), 2)
                records.append((date, f"P{p+1:03d}", f"{PRODUCT_NAMES[p % len(PRODUCT_NAMES)]} {p+1:02d}", category, f"S{s+1:02d}", f"Store {s+1:02d}", region, sold, unit_price, discount, promotion, holiday, "Rain" if rng.random() < 0.12 else "Clear", stock, supplier, lead_time, returns, round(base_price * cost_ratio, 2), requested > sold))
    frame = pd.DataFrame.from_records(records, columns=["date", "product_id", "product", "category", "store_id", "store", "region", "units", "price", "discount", "promotion", "holiday", "weather", "stock", "supplier", "lead_time", "returns", "unit_cost", "stockout"])
    return enrich(frame)


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ("units", "price", "stock", "discount", "lead_time", "returns", "unit_cost"):
        if col in result:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    if "returns" not in result:
        result["returns"] = 0
    if "unit_cost" not in result:
        result["unit_cost"] = result["price"] * 0.7
    if "discount" not in result:
        result["discount"] = 0.0
    if "promotion" not in result:
        result["promotion"] = result["discount"].fillna(0).gt(0)
    for col, fallback in {"product": "Unknown product", "category": "Unknown", "store": "Unknown store", "region": "Unknown", "supplier": "Unknown", "weather": "Unknown"}.items():
        if col not in result:
            result[col] = fallback
    if "lead_time" not in result:
        result["lead_time"] = 7
    if "stockout" not in result:
        result["stockout"] = result["stock"].fillna(0).le(0)
    result["revenue"] = result["units"] * result["price"]
    result["profit"] = result["units"] * (result["price"] - result["unit_cost"])
    return result


def read_sales_csv(source: bytes | BytesIO) -> pd.DataFrame:
    try:
        raw = pd.read_csv(BytesIO(source) if isinstance(source, bytes) else source)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"The CSV could not be read: {exc}") from exc
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    if raw.empty:
        raise ValueError("The CSV has no rows.")
    return enrich(raw)


def assess_quality(frame: pd.DataFrame) -> QualityReport:
    rows, columns = frame.shape
    if not rows:
        return QualityReport(0, columns, 0, 0, 0, 0, 0, 0, 0, 0, ("Dataset is empty",))
    missing = float(frame.isna().sum().sum() / (rows * columns) * 100)
    duplicates = int(frame.duplicated(subset=[c for c in ("date", "product_id", "store_id") if c in frame]).sum())
    dates = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = int(dates.isna().sum())
    units = pd.to_numeric(frame["units"], errors="coerce")
    stock = pd.to_numeric(frame["stock"], errors="coerce")
    negative_units = int(units.lt(0).sum())
    negative_stock = int(stock.lt(0).sum())
    q1, q3 = units.quantile([0.25, 0.75])
    outliers = int(units.gt(q3 + 3 * (q3 - q1)).sum()) if pd.notna(q1) else 0
    missing_ids = int((frame["product_id"].isna() | frame["store_id"].isna()).sum())
    issues = []
    for count, label in ((duplicates, "duplicate product/store/date keys"), (invalid_dates, "invalid dates"), (negative_units, "negative unit sales"), (negative_stock, "negative stock values"), (missing_ids, "missing entity IDs"), (outliers, "extreme unit outliers")):
        if count:
            issues.append(f"{count:,} {label}")
    if missing:
        issues.append(f"{missing:.2f}% missing cells")
    defect_rate = (duplicates + invalid_dates + negative_units + negative_stock + missing_ids + outliers) / rows
    score = int(max(0, min(100, round(100 - missing * 2 - defect_rate * 100))))
    return QualityReport(rows, columns, missing, duplicates, invalid_dates, negative_units, negative_stock, outliers, missing_ids, score, tuple(issues))


def clean_data(frame: pd.DataFrame, cap_outliers: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a cleaned copy and an explicit operation log; never mutate input."""
    data = frame.copy()
    log = []
    before = len(data)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date", "product_id", "store_id"])
    log.append(("Quarantine invalid dates or missing IDs", before - len(data)))
    before = len(data)
    data = data.drop_duplicates(subset=["date", "product_id", "store_id"], keep="last")
    log.append(("Remove duplicate entity/date keys", before - len(data)))
    for col in ("units", "stock", "price"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
        bad = int(data[col].lt(0).sum())
        if bad:
            data.loc[data[col].lt(0), col] = np.nan
        count = int(data[col].isna().sum())
        median = data[col].median()
        data[col] = data[col].fillna(0 if pd.isna(median) else median)
        log.append((f"Replace invalid or missing {col} with median", count))
    for col in ("product", "category", "store", "region", "supplier", "weather"):
        if col in data:
            count = int(data[col].isna().sum())
            data[col] = data[col].fillna("Unknown")
            log.append((f"Fill missing {col} as Unknown", count))
    if cap_outliers:
        cap = data["units"].quantile(0.99)
        count = int(data["units"].gt(cap).sum())
        data["units"] = data["units"].clip(upper=cap)
        log.append(("Cap units at 99th percentile", count))
    return enrich(data).reset_index(drop=True), pd.DataFrame(log, columns=["operation", "affected_rows"])

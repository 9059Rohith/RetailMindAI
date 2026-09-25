"""Synthetic data, ingestion, validation, and explicit cleaning."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib

import numpy as np
import pandas as pd

REQUIRED = {"date", "product_id", "store_id", "units", "price", "stock"}
CATEGORIES = ("Grocery", "Apparel", "Electronics", "Home", "Beauty", "Sports")
REGIONS = ("North", "South", "East", "West")
PRODUCT_NAMES = ("Daily essentials", "Signature blend", "Core collection", "Premium kit", "Everyday line", "Seasonal edit", "Active series", "Classic range", "Fresh pick", "Studio edition")


@dataclass(frozen=True)
class QualityCheck:
    check: str
    severity: str
    affected_rows: int
    recommended_action: str


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
    checks: tuple[QualityCheck, ...] = ()


@dataclass(frozen=True)
class BenchmarkImport:
    """A bounded M5 sample and explicit provenance/availability notes."""

    data: pd.DataFrame
    series_count: int
    days: int
    missing_prices: int


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


def dataset_metadata(frame: pd.DataFrame, source: str, created_at: str | None = None) -> dict[str, str | int | None]:
    """Stable content identity for the exact rows and columns in a session."""
    canonical = frame.reindex(sorted(frame.columns), axis=1).reset_index(drop=True)
    digest = hashlib.sha256(pd.util.hash_pandas_object(canonical, index=True).values.tobytes()).hexdigest()
    return {"dataset_id": digest[:12], "checksum": digest, "source": source, "created_at": created_at,
            "row_count": len(frame), "column_count": len(frame.columns),
            "quality_score": assess_quality(frame).score}


def read_m5_sample(sales_csv: bytes | BytesIO, calendar_csv: bytes | BytesIO, prices_csv: bytes | BytesIO,
                   max_series: int = 24, max_days: int = 180) -> BenchmarkImport:
    """Normalize a bounded sample of the official M5 wide-table format.

    The source files are not redistributed. Stock and unit cost are unavailable
    in M5 and deliberately remain missing in the returned data.
    """
    if max_series < 1 or max_days < 1:
        raise ValueError("Choose positive M5 series and day limits.")
    def source(value: bytes | BytesIO) -> BytesIO:
        stream = BytesIO(value) if isinstance(value, bytes) else value
        stream.seek(0)
        return stream

    try:
        sales = pd.read_csv(source(sales_csv), nrows=max_series)
        calendar = pd.read_csv(source(calendar_csv))
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"M5 file could not be read: {exc}") from exc
    identity = {"item_id", "store_id", "state_id", "cat_id"}
    if not identity.issubset(sales) or not {"d", "date", "wm_yr_wk"}.issubset(calendar):
        raise ValueError("M5 sales needs item_id/store_id/state_id/cat_id; calendar needs d/date/wm_yr_wk.")
    day_columns = sorted((col for col in sales if col.startswith("d_") and col[2:].isdigit()),
                         key=lambda col: int(col[2:]))[-max_days:]
    if sales.empty or not day_columns:
        raise ValueError("M5 sales has no selected series or d_ day columns.")
    dates = calendar[["d", "date", "wm_yr_wk"]].drop_duplicates("d")
    if not set(day_columns).issubset(set(dates.d)):
        raise ValueError("M5 calendar does not cover every selected sales day.")
    long = sales[list(identity) + day_columns].melt(id_vars=list(identity), value_vars=day_columns,
                                                    var_name="d", value_name="units")
    long = long.merge(dates, on="d", how="left", validate="many_to_one")
    pair_keys = sales[["item_id", "store_id"]].drop_duplicates()
    item_ids = set(pair_keys.item_id)
    store_ids = set(pair_keys.store_id)
    weeks = set(dates.loc[dates.d.isin(day_columns), "wm_yr_wk"])
    matches = []
    try:
        for chunk in pd.read_csv(source(prices_csv), chunksize=100_000):
            required = {"store_id", "item_id", "wm_yr_wk", "sell_price"}
            if not required.issubset(chunk):
                raise ValueError("M5 prices needs store_id/item_id/wm_yr_wk/sell_price.")
            chosen = chunk[chunk.item_id.isin(item_ids) & chunk.store_id.isin(store_ids)
                           & chunk.wm_yr_wk.isin(weeks)]
            if not chosen.empty:
                matches.append(chosen[list(required)])
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError(f"M5 prices file could not be read: {exc}") from exc
    if not matches:
        raise ValueError("No M5 prices match the selected products, stores and calendar weeks.")
    prices = pd.concat(matches, ignore_index=True).drop_duplicates(["store_id", "item_id", "wm_yr_wk"])
    long = long.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left", validate="many_to_one")
    frame = pd.DataFrame({"date": long.date, "product_id": long.item_id, "product": long.item_id,
                          "category": long.cat_id, "store_id": long.store_id, "store": long.store_id,
                          "region": long.state_id, "units": long.units, "price": long.sell_price,
                          "stock": np.nan, "unit_cost": np.nan, "stockout": False,
                          "supplier": "Not supplied", "lead_time": 7})
    frame = enrich(frame)
    if frame.date.isna().any() or frame.units.isna().any():
        raise ValueError("M5 sample has invalid calendar dates or sales quantities.")
    return BenchmarkImport(frame, len(pair_keys), len(day_columns), int(frame.price.isna().sum()))


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


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ("units", "price", "stock", "discount", "lead_time", "returns", "unit_cost", "latitude", "longitude"):
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
    else:
        result["promotion"] = result["promotion"].astype(str).str.lower().isin({"true", "1", "yes"})
    if "holiday" in result:
        result["holiday"] = result["holiday"].astype(str).str.lower().isin({"true", "1", "yes"})
    for col, fallback in {"product": "Unknown product", "category": "Unknown", "store": "Unknown store", "region": "Unknown", "supplier": "Unknown", "weather": "Unknown"}.items():
        if col not in result:
            result[col] = fallback
    if "lead_time" not in result:
        result["lead_time"] = 7
    if "stockout" not in result:
        result["stockout"] = result["stock"].fillna(0).le(0)
    else:
        result["stockout"] = result["stockout"].astype(str).str.lower().isin({"true", "1", "yes"})
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
    missing_ids = int((frame["product_id"].isna() | frame["store_id"].isna()
                       | frame["product_id"].astype(str).str.strip().eq("")
                       | frame["store_id"].astype(str).str.strip().eq("")).sum())
    invalid_numeric = int(sum(pd.to_numeric(frame[col], errors="coerce").isna().sum()
                              for col in ("units", "price", "stock") if col in frame))
    product_conflicts = int(frame.groupby("product_id")[["product", "category"]].nunique(dropna=True).gt(1).any(axis=1).sum())
    store_conflicts = int(frame.groupby("store_id")[["store", "region"]].nunique(dropna=True).gt(1).any(axis=1).sum())
    constant = int(sum(frame[col].nunique(dropna=True) <= 1 for col in frame if col not in {"date", "product_id", "store_id"}))
    suspicious = int(units.fillna(0).eq(0).mean() > 0.9)
    issues = []
    for count, label in ((duplicates, "duplicate product/store/date keys"), (invalid_dates, "invalid dates"),
                         (invalid_numeric, "missing or invalid required numbers"), (negative_units, "negative unit sales"),
                         (negative_stock, "negative stock values"), (missing_ids, "missing entity IDs"),
                         (product_conflicts + store_conflicts, "inconsistent entity descriptions"),
                         (outliers, "extreme unit outliers")):
        if count:
            issues.append(f"{count:,} {label}")
    if missing:
        issues.append(f"{missing:.2f}% missing cells")
    defect_rate = (duplicates + invalid_dates + invalid_numeric + negative_units + negative_stock + missing_ids
                   + product_conflicts + store_conflicts + outliers) / rows
    score = int(max(0, min(100, round(100 - missing * 2 - defect_rate * 100))))
    specifications = (
        ("Missing cells", "Warning", int(frame.isna().any(axis=1).sum()), "Review source and imputation policy."),
        ("Duplicate entity/date keys", "Warning", duplicates, "Deduplicate after choosing the correct record."),
        ("Invalid dates", "Critical", invalid_dates, "Correct dates or quarantine affected rows."),
        ("Missing/invalid required numbers", "Critical", invalid_numeric, "Repair sales, price or stock fields."),
        ("Negative unit sales", "Critical", negative_units, "Check returns or data entry; do not treat as demand."),
        ("Negative stock", "Critical", negative_stock, "Reconcile inventory snapshots."),
        ("Missing entity IDs", "Critical", missing_ids, "Supply product and store identifiers."),
        ("Entity description conflicts", "Warning", product_conflicts + store_conflicts, "Reconcile product and store master data."),
        ("Extreme unit outliers", "Warning", outliers, "Investigate unusual transactions before capping."),
        ("Constant descriptive columns", "Info", constant, "Confirm the dataset is intentionally scoped."),
        ("Over 90% zero-unit rows", "Info", suspicious, "Check intermittency and the meaning of zero sales."),
    )
    checks = tuple(QualityCheck(*item) for item in specifications)
    return QualityReport(rows, columns, missing, duplicates, invalid_dates, negative_units, negative_stock,
                         outliers, missing_ids, score, tuple(issues), checks)


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
        if pd.isna(median):
            log.append((f"Keep {col} missing because no observed value exists", count))
        else:
            data[col] = data[col].fillna(median)
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

"""Observed retail data ingestion, validation, and explicit cleaning."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib

import numpy as np
import pandas as pd

REQUIRED = {"date", "product_id", "store_id", "units"}


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
    event_columns = [column for column in ("event_name_1", "event_name_2") if column in calendar]
    if event_columns:
        calendar["holiday"] = calendar[event_columns].notna().any(axis=1)
    dates = calendar[["d", "date", "wm_yr_wk"] + (["holiday"] if event_columns else [])].drop_duplicates("d")
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
                          "stock": np.nan, "unit_cost": np.nan})
    if "holiday" in long:
        frame["holiday"] = long.holiday
    frame = enrich(frame)
    if frame.date.isna().any() or frame.units.isna().any():
        raise ValueError("M5 sample has invalid calendar dates or sales quantities.")
    return BenchmarkImport(frame, len(pair_keys), len(day_columns), int(frame.price.isna().sum()))


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ("units", "price", "stock", "discount", "lead_time", "returns", "unit_cost", "latitude", "longitude"):
        if col in result:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    for col in ("price", "stock", "discount", "lead_time", "returns", "unit_cost"):
        if col not in result:
            result[col] = np.nan
    for col in ("promotion", "holiday", "stockout"):
        if col in result:
            result[col] = result[col].map(lambda value: pd.NA if pd.isna(value) else
                                          str(value).strip().lower() in {"true", "1", "yes"}).astype("boolean")
        else:
            result[col] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    if result["promotion"].isna().all() and result["discount"].notna().any():
        result["promotion"] = result["discount"].gt(0).where(result["discount"].notna()).astype("boolean")
    if result["stockout"].isna().all() and result["stock"].notna().any():
        result["stockout"] = result["stock"].le(0).where(result["stock"].notna()).astype("boolean")
    result["product"] = result.get("product", result["product_id"]).fillna(result["product_id"])
    result["store"] = result.get("store", result["store_id"]).fillna(result["store_id"])
    for col in ("category", "region", "supplier", "weather"):
        if col not in result:
            result[col] = pd.NA
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
    missing = float(frame[list(REQUIRED)].isna().sum().sum() / (rows * len(REQUIRED)) * 100)
    duplicates = int(frame.duplicated(subset=[c for c in ("date", "product_id", "store_id") if c in frame]).sum())
    dates = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = int(dates.isna().sum())
    units = pd.to_numeric(frame["units"], errors="coerce")
    stock = pd.to_numeric(frame["stock"], errors="coerce") if "stock" in frame else pd.Series(np.nan, index=frame.index)
    negative_units = int(units.lt(0).sum())
    negative_stock = int(stock.lt(0).sum())
    q1, q3 = units.quantile([0.25, 0.75])
    outliers = int(units.gt(q3 + 3 * (q3 - q1)).sum()) if pd.notna(q1) else 0
    missing_ids = int((frame["product_id"].isna() | frame["store_id"].isna()
                       | frame["product_id"].astype(str).str.strip().eq("")
                       | frame["store_id"].astype(str).str.strip().eq("")).sum())
    invalid_numeric = int(pd.to_numeric(frame["units"], errors="coerce").isna().sum())
    product_fields = [col for col in ("product", "category") if col in frame]
    store_fields = [col for col in ("store", "region") if col in frame]
    product_conflicts = int(frame.groupby("product_id")[product_fields].nunique(dropna=True).gt(1).any(axis=1).sum()) if product_fields else 0
    store_conflicts = int(frame.groupby("store_id")[store_fields].nunique(dropna=True).gt(1).any(axis=1).sum()) if store_fields else 0
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
        issues.append(f"{missing:.2f}% missing required cells")
    defect_rate = (duplicates + invalid_dates + invalid_numeric + negative_units + negative_stock + missing_ids
                   + product_conflicts + store_conflicts + outliers) / rows
    score = int(max(0, min(100, round(100 - missing * 2 - defect_rate * 100))))
    specifications = (
        ("Missing required cells", "Warning", int(frame[list(REQUIRED)].isna().any(axis=1).sum()), "Review source records; optional fields remain unavailable."),
        ("Duplicate entity/date keys", "Warning", duplicates, "Deduplicate after choosing the correct record."),
        ("Invalid dates", "Critical", invalid_dates, "Correct dates or quarantine affected rows."),
        ("Missing/invalid required numbers", "Critical", invalid_numeric, "Repair observed unit sales."),
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
    """Quarantine invalid records while preserving every observed numeric value."""
    data = frame.copy()
    log = []
    before = len(data)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["units"] = pd.to_numeric(data["units"], errors="coerce")
    data = data.dropna(subset=["date", "product_id", "store_id", "units"])
    data = data[data.units.ge(0)]
    log.append(("Quarantine invalid dates, IDs, missing or negative sales", before - len(data)))
    before = len(data)
    data = data.drop_duplicates(subset=["date", "product_id", "store_id"], keep="last")
    log.append(("Remove duplicate entity/date keys", before - len(data)))
    for col in ("stock", "price", "unit_cost"):
        if col in data:
            data[col] = pd.to_numeric(data[col], errors="coerce")
            count = int(data[col].lt(0).sum())
            data.loc[data[col].lt(0), col] = np.nan
            if count:
                log.append((f"Mark invalid negative {col} as unavailable", count))
    if cap_outliers:
        raise ValueError("Capping would alter observed sales and is disabled for real data.")
    return enrich(data).reset_index(drop=True), pd.DataFrame(log, columns=["operation", "affected_rows"])

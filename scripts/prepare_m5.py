"""Build a reproducible, observed M5 subset for the deployable application."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(source: Path, output: Path, per_group: int = 5, days: int = 731) -> dict:
    sales_path = source / "sales_train_evaluation.csv"
    calendar_path = source / "calendar.csv"
    prices_path = source / "sell_prices.csv"
    for path in (sales_path, calendar_path, prices_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    identity = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]
    keys = pd.read_csv(sales_path, usecols=identity)
    if keys.duplicated(["item_id", "store_id"]).any():
        raise ValueError("Duplicate product/store series in source sales")
    keys["rank"] = keys.apply(lambda row: hashlib.sha256(f"{row['store_id']}|{row['cat_id']}|{row['item_id']}".encode()).hexdigest(), axis=1)
    selected = keys.sort_values("rank").groupby(["store_id", "cat_id"], sort=True).head(per_group)
    selected_pairs = set(zip(selected.item_id, selected.store_id))
    header = pd.read_csv(sales_path, nrows=0).columns.tolist()
    day_cols = sorted((col for col in header if col.startswith("d_") and col[2:].isdigit()), key=lambda col: int(col[2:]))[-days:]
    chunks = []
    for chunk in pd.read_csv(sales_path, usecols=identity + day_cols, chunksize=500):
        keep = [pair in selected_pairs for pair in zip(chunk.item_id, chunk.store_id)]
        if any(keep):
            chunks.append(chunk.loc[keep])
    sales = pd.concat(chunks, ignore_index=True)
    if len(sales) != len(selected):
        raise ValueError("Selected sales series did not match source")
    calendar = pd.read_csv(calendar_path)
    if calendar.d.duplicated().any():
        raise ValueError("Duplicate calendar day")
    calendar["holiday"] = calendar[["event_name_1", "event_name_2"]].notna().any(axis=1)
    calendar = calendar[["d", "date", "wm_yr_wk", "holiday", "event_name_1", "event_name_2"]]
    long = sales.melt(id_vars=identity, value_vars=day_cols, var_name="d", value_name="units")
    long = long.merge(calendar, on="d", how="left", validate="many_to_one")
    if long.date.isna().any():
        raise ValueError("Missing selected calendar dates")
    item_ids, store_ids, weeks = set(selected.item_id), set(selected.store_id), set(long.wm_yr_wk)
    price_chunks = []
    for chunk in pd.read_csv(prices_path, chunksize=100_000):
        chosen = chunk[chunk.item_id.isin(item_ids) & chunk.store_id.isin(store_ids) & chunk.wm_yr_wk.isin(weeks)]
        if not chosen.empty:
            price_chunks.append(chosen)
    prices = pd.concat(price_chunks, ignore_index=True)
    if prices.duplicated(["store_id", "item_id", "wm_yr_wk"]).any():
        raise ValueError("Duplicate observed price key")
    long = long.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left", validate="many_to_one")
    frame = long.rename(columns={"item_id": "product_id", "cat_id": "category", "state_id": "region", "sell_price": "price"})
    frame = frame[["date", "product_id", "dept_id", "category", "store_id", "region", "units", "price", "holiday", "event_name_1", "event_name_2"]]
    frame = frame.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    if frame.duplicated(["date", "product_id", "store_id"]).any():
        raise ValueError("Duplicate final observation key")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, compression={"method": "gzip", "mtime": 0})
    profile = {"source": "M5 Forecasting Accuracy, sales_train_evaluation, calendar, sell_prices", "source_url": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data", "method": "Five series per observed store/category group ranked by SHA-256(store|category|item); last 731 observed sales days; left join observed weekly prices and calendar events; no imputation", "raw_sha256": {p.name: sha256(p) for p in (sales_path, calendar_path, prices_path)}, "sample_sha256": sha256(output), "rows": len(frame), "series": len(selected), "days": len(day_cols), "date_start": str(frame.date.min()), "date_end": str(frame.date.max()), "missing_prices": int(frame.price.isna().sum()), "missing_stock": "not present in M5", "missing_unit_cost": "not present in M5"}
    output.with_name("m5_source.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Directory holding the three official M5 CSV files")
    parser.add_argument("--output", type=Path, default=Path("data/m5_observed.csv.gz"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))

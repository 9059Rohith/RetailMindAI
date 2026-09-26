"""Optional SQL persistence with a safe SQLite fallback."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def database_engine() -> tuple[Engine, str]:
    mode = os.getenv("DATABASE_MODE", "sqlite").lower()
    if mode == "mysql":
        url = (f"mysql+pymysql://{quote_plus(os.getenv('MYSQL_USER', 'retailmind'))}:"
               f"{quote_plus(os.getenv('MYSQL_PASSWORD', ''))}@{os.getenv('MYSQL_HOST', 'localhost')}:"
               f"{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE', 'retailmind')}")
        try:
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return engine, "mysql"
        except Exception:
            pass
    sqlite_path = Path(os.getenv("SQLITE_PATH", "retailmind.db"))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{sqlite_path.as_posix()}", connect_args={"timeout": 30}), "sqlite"


def save_sales(data: pd.DataFrame, engine: Engine) -> None:
    if engine.dialect.name == "mysql":
        _save_mysql_dimensions_and_facts(data, engine)
    staging = f"sales_snapshot_stage_{uuid4().hex[:12]}"
    backup = f"sales_snapshot_backup_{uuid4().hex[:12]}"
    try:
        # Build the complete replacement before touching the current snapshot.
        data.to_sql(staging, engine, if_exists="fail", index=False, chunksize=1000)
        with engine.begin() as connection:
            existing = inspect(connection).has_table("sales_snapshot")
            if engine.dialect.name == "mysql":
                if existing:
                    connection.execute(text(f"RENAME TABLE sales_snapshot TO {backup}, {staging} TO sales_snapshot"))
                else:
                    connection.execute(text(f"RENAME TABLE {staging} TO sales_snapshot"))
            else:
                if existing:
                    connection.execute(text(f"ALTER TABLE sales_snapshot RENAME TO {backup}"))
                connection.execute(text(f"ALTER TABLE {staging} RENAME TO sales_snapshot"))
        if existing:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE {backup}"))
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {staging}"))


def _save_mysql_dimensions_and_facts(data: pd.DataFrame, engine: Engine) -> None:
    """Populate the normalized academic schema alongside the UI snapshot."""
    source = data.copy()
    source["date"] = pd.to_datetime(source["date"], errors="coerce")
    if source.date.isna().any() or source.duplicated(["date", "product_id", "store_id"]).any():
        raise ValueError("Clean invalid dates and duplicate product/store/day keys before saving to MySQL.")
    if (source.units < 0).any() or (source.stock.dropna() < 0).any():
        raise ValueError("Clean negative units or stock before saving to MySQL.")
    def scalar(value):
        return None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value
    def execute(connection, sql: str, rows: list[dict]) -> None:
        if rows:
            connection.execute(text(sql), rows)
    category = source.category.dropna().astype(str).unique()
    region = source.region.dropna().astype(str).unique()
    supplier = source.supplier.dropna().astype(str).unique()
    with engine.begin() as connection:
        # The UI stores one current dataset, so facts must mirror its snapshot.
        # Keep dimensions for existing forecast/model references.
        for table in ("promotions", "prices", "sales", "inventory"):
            connection.execute(text(f"DELETE FROM {table}"))
        execute(connection, "INSERT INTO categories(category_id,category_name) VALUES (:id,:name) ON DUPLICATE KEY UPDATE category_name=VALUES(category_name)",
                [{"id": item, "name": item} for item in sorted(category)])
        execute(connection, "INSERT INTO regions(region_id,region_name) VALUES (:id,:name) ON DUPLICATE KEY UPDATE region_name=VALUES(region_name)",
                [{"id": item, "name": item} for item in sorted(region)])
        execute(connection, "INSERT INTO suppliers(supplier_id,supplier_name) VALUES (:id,:name) ON DUPLICATE KEY UPDATE supplier_name=VALUES(supplier_name)",
                [{"id": item, "name": item} for item in sorted(supplier)])
        product_rows = source.drop_duplicates("product_id", keep="last")
        execute(connection, "INSERT INTO products(product_id,product_name,category_id,supplier_id) VALUES (:id,:name,:category,:supplier) ON DUPLICATE KEY UPDATE product_name=VALUES(product_name),category_id=VALUES(category_id),supplier_id=VALUES(supplier_id)",
                [{"id": str(row.product_id), "name": str(row.product), "category": scalar(row.category), "supplier": scalar(row.supplier)}
                 for row in product_rows.itertuples()])
        store_rows = source.drop_duplicates("store_id", keep="last")
        execute(connection, "INSERT INTO stores(store_id,store_name,region_id,latitude,longitude) VALUES (:id,:name,:region,:latitude,:longitude) ON DUPLICATE KEY UPDATE store_name=VALUES(store_name),region_id=VALUES(region_id),latitude=VALUES(latitude),longitude=VALUES(longitude)",
                [{"id": str(row.store_id), "name": str(row.store), "region": scalar(row.region),
                  "latitude": scalar(getattr(row, "latitude", None)), "longitude": scalar(getattr(row, "longitude", None))}
                 for row in store_rows.itertuples()])
        days = source.groupby("date", as_index=False).agg(holiday=("holiday", "max"))
        execute(connection, "INSERT INTO calendar(calendar_date,weekday_num,month_num,year_num,holiday) VALUES (:date,:weekday,:month,:year,:holiday) ON DUPLICATE KEY UPDATE holiday=VALUES(holiday)",
                [{"date": row.date.date(), "weekday": int(row.date.dayofweek), "month": int(row.date.month),
                  "year": int(row.date.year), "holiday": scalar(row.holiday)}
                 for row in days.itertuples()])
        execute(connection, "INSERT INTO promotions(product_id,store_id,start_date,end_date,discount_rate) VALUES (:product,:store,:date,:date,:discount)",
                [{"product": str(row.product_id), "store": str(row.store_id), "date": row.date.date(),
                  "discount": scalar(row.discount)}
                 for row in source[source.promotion.fillna(False)].itertuples()])
        price_rows = source[source.price.notna()]
        execute(connection, "INSERT INTO prices(product_id,store_id,effective_date,unit_price) VALUES (:product,:store,:date,:price) ON DUPLICATE KEY UPDATE unit_price=VALUES(unit_price)",
                [{"product": str(row.product_id), "store": str(row.store_id), "date": row.date.date(),
                  "price": float(row.price)} for row in price_rows.itertuples()])
        execute(connection, "INSERT INTO sales(sale_date,product_id,store_id,units,unit_price,returns_units,promotion) VALUES (:date,:product,:store,:units,:price,:returns,:promotion) ON DUPLICATE KEY UPDATE units=VALUES(units),unit_price=VALUES(unit_price),returns_units=VALUES(returns_units),promotion=VALUES(promotion)",
                [{"date": row.date.date(), "product": str(row.product_id), "store": str(row.store_id),
                  "units": float(row.units), "price": scalar(row.price), "returns": scalar(row.returns),
                  "promotion": scalar(row.promotion)} for row in source.itertuples()])
        execute(connection, "INSERT INTO inventory(snapshot_date,product_id,store_id,on_hand,lead_time_days) VALUES (:date,:product,:store,:stock,:lead) ON DUPLICATE KEY UPDATE on_hand=VALUES(on_hand),lead_time_days=VALUES(lead_time_days)",
                [{"date": row.date.date(), "product": str(row.product_id), "store": str(row.store_id),
                  "stock": scalar(row.stock), "lead": scalar(row.lead_time)}
                 for row in source[source.stock.notna() | source.lead_time.notna()].itertuples()])


def load_sales(engine: Engine) -> pd.DataFrame:
    with engine.connect() as connection:
        data = pd.read_sql(text("SELECT * FROM sales_snapshot"), connection)
    if "date" in data:
        data["date"] = pd.to_datetime(data["date"])
    return data

"""Optional SQL persistence with a safe SQLite fallback."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
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
    return create_engine(f"sqlite:///{sqlite_path.as_posix()}"), "sqlite"


def save_sales(data: pd.DataFrame, engine: Engine) -> None:
    data.to_sql("sales_snapshot", engine, if_exists="replace", index=False, chunksize=1000, method="multi")


def load_sales(engine: Engine) -> pd.DataFrame:
    with engine.connect() as connection:
        data = pd.read_sql(text("SELECT * FROM sales_snapshot"), connection)
    if "date" in data:
        data["date"] = pd.to_datetime(data["date"])
    return data

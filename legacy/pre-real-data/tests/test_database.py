import pandas as pd
import pytest

from retailmind.data import generate_retail_data
from retailmind.database import database_engine, load_sales, save_sales


def test_sqlite_round_trip_and_mysql_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_MODE", "mysql")
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "1")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "retailmind.db"))
    engine, mode = database_engine()
    assert mode == "sqlite"
    source = generate_retail_data(products=1, stores=1, days=7)
    save_sales(source, engine)
    loaded = load_sales(engine)
    assert len(loaded) == 7
    assert loaded.revenue.sum() == source.revenue.sum()


def test_failed_snapshot_write_preserves_previous_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_MODE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "safe.db"))
    engine, _ = database_engine()
    source = generate_retail_data(products=1, stores=1, days=7)
    save_sales(source, engine)
    original_to_sql = pd.DataFrame.to_sql

    def failed_write(self, name, *args, **kwargs):
        if name.startswith("sales_snapshot_stage_"):
            raise RuntimeError("simulated write failure")
        return original_to_sql(self, name, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_sql", failed_write)
    with pytest.raises(RuntimeError, match="simulated"):
        save_sales(source.iloc[:2], engine)
    loaded = load_sales(engine)
    assert len(loaded) == len(source)
    assert loaded.revenue.sum() == source.revenue.sum()

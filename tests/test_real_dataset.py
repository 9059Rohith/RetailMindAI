"""End-to-end guards for the committed observed M5 subset."""
import hashlib
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from streamlit.testing.v1 import AppTest

from retailmind.analytics import kpis
from retailmind.data import assess_quality, enrich
from retailmind.database import load_sales, save_sales
from retailmind.forecast import daily_series, run_forecast

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "m5_observed.csv.gz"


def observed():
    return enrich(pd.read_csv(DATA, low_memory=False))


def test_bundled_records_are_real_complete_keys_and_preserve_missing_fields():
    profile = json.loads((ROOT / "data" / "m5_source.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == profile["sample_sha256"]
    data = observed()
    assert (len(data), data.groupby(["product_id", "store_id"]).ngroups, data.store_id.nunique()) == (109650, 150, 10)
    assert (str(data.date.min().date()), str(data.date.max().date())) == ("2014-05-23", "2016-05-22")
    assert not data.duplicated(["date", "product_id", "store_id"]).any()
    assert data.units.sum() == 105840
    assert data.price.isna().sum() == 863
    assert data.stock.isna().all() and data.unit_cost.isna().all() and data.stockout.isna().all()
    assert data.promotion.isna().all() and data.lead_time.isna().all()
    assert kpis(data)["revenue"] == 414479.4
    assert pd.isna(kpis(data)["profit"])
    quality = assess_quality(data)
    assert quality.missing_pct == 0 and quality.duplicates == 0 and quality.invalid_dates == 0
    assert not (ROOT / "data" / "demo_sales.csv").exists()


def test_real_product_forecast_uses_measured_history():
    data = observed()
    product, store = data.groupby(["product_id", "store_id"]).units.sum().idxmax()
    series = daily_series(data, product, store)
    result = run_forecast(series, horizon=7, include_ml=False, include_statistical=False)
    assert len(result.future) == 7
    assert result.future.date.min().date().isoformat() == "2016-05-23"
    assert result.comparison.WAPE.notna().any()
    assert result.future.forecast.ge(0).all()


def test_real_records_round_trip_without_inventing_missing_fields(tmp_path):
    rows = observed().head(40)
    engine = create_engine(f"sqlite:///{(tmp_path / 'observed.db').as_posix()}")
    save_sales(rows, engine)
    loaded = load_sales(engine)
    assert len(loaded) == 40
    assert loaded.stock.isna().all() and loaded.unit_cost.isna().all()
    assert loaded.price.isna().sum() == rows.price.isna().sum()


def test_all_real_data_pages_render_without_unsupported_metrics():
    app = AppTest.from_file(ROOT / "app" / "main.py", default_timeout=120).run()
    assert not app.exception
    assert any(metric.label == "Observed revenue" for metric in app.metric)
    navigator = next(radio for radio in app.radio if radio.label == "Workspace")
    for page in ("Data studio", "Analytics", "Forecast lab", "Inventory", "Insights", "Reports"):
        app = navigator.set_value(page).run()
        assert not app.exception, page
        navigator = next(radio for radio in app.radio if radio.label == "Workspace")
    app = navigator.set_value("Analytics").run()
    assert not any(metric.label in {"Gross profit", "Recorded returns"} for metric in app.metric)

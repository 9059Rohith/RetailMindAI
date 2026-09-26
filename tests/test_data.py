from io import BytesIO

import pandas as pd
import pytest

from retailmind.data import assess_quality, clean_data, dataset_metadata, read_m5_sample, read_sales_csv
from tests.synthetic_fixtures import SyntheticConfig, generate_retail_data


def test_generator_is_deterministic_and_retail_complete():
    first = generate_retail_data(products=3, stores=2, days=35, seed=7)
    second = generate_retail_data(products=3, stores=2, days=35, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 210
    assert {"revenue", "profit", "stockout", "promotion", "region", "lead_time"}.issubset(first)
    assert (first["units"] >= 0).all()


def test_generator_controls_change_scope_without_losing_reproducibility():
    config = SyntheticConfig(regions=2, categories=2, end_date="2026-01-31", promotion_frequency=0.2,
                             price_variation=0.1, demand_volatility=1.5, stockout_probability=0.2,
                             slow_mover_share=0.3)
    first = generate_retail_data(3, 3, 40, 9, config)
    second = generate_retail_data(3, 3, 40, 9, config)
    pd.testing.assert_frame_equal(first, second)
    assert first.region.nunique() == 2
    assert first.category.nunique() == 2
    assert first.date.max() == pd.Timestamp("2026-01-31")
    assert first.price.nunique() > 3


def test_quality_and_cleaning_keep_original():
    source = generate_retail_data(products=1, stores=1, days=35)
    bad = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    bad.loc[1, "stock"] = -4
    bad.loc[2, "units"] = -2
    bad["date"] = bad["date"].astype(object)
    bad.loc[3, "date"] = "bad-date"
    report = assess_quality(bad)
    assert report.duplicates >= 1
    assert report.negative_units == 1
    assert any(check.check == "Negative unit sales" and check.severity == "Critical" and check.affected_rows == 1
               for check in report.checks)
    cleaned, log = clean_data(bad)
    assert len(cleaned) < len(bad)
    assert (cleaned.stock.dropna() >= 0).all()
    assert cleaned.stock.isna().sum() == 1
    assert (cleaned.units >= 0).all()
    assert len(log) > 0
    assert bad.loc[1, "stock"] == -4


def test_bad_csv_gets_actionable_error():
    with pytest.raises(ValueError, match="Missing required columns"):
        read_sales_csv(b"date,units\n2025-01-01,2\n")


def test_m5_import_preserves_provenance_and_missing_inventory():
    sales = b"item_id,cat_id,store_id,state_id,d_1,d_2,d_3\nFOOD_1,FOODS,CA_1,CA,2,3,4\nFOOD_2,FOODS,TX_1,TX,0,1,2\n"
    calendar = b"d,date,wm_yr_wk\nd_1,2011-01-29,11101\nd_2,2011-01-30,11101\nd_3,2011-01-31,11102\n"
    prices = b"store_id,item_id,wm_yr_wk,sell_price\nCA_1,FOOD_1,11101,2.5\nCA_1,FOOD_1,11102,3\nTX_1,FOOD_2,11101,1.5\nTX_1,FOOD_2,11102,2\n"
    imported = read_m5_sample(sales, calendar, prices, max_series=2, max_days=2)
    assert (imported.series_count, imported.days, imported.missing_prices) == (2, 2, 0)
    assert len(imported.data) == 4
    assert imported.data.stock.isna().all()
    assert imported.data.unit_cost.isna().all()
    assert imported.data.loc[imported.data.product_id.eq("FOOD_1"), "revenue"].sum() == 19.5
    version = dataset_metadata(imported.data, "M5 sample")
    assert version["dataset_id"] == dataset_metadata(imported.data.copy(), "M5 sample")["dataset_id"]
    streamed = read_m5_sample(BytesIO(sales), BytesIO(calendar), BytesIO(prices), max_series=2, max_days=2)
    assert streamed.data.equals(imported.data)
    with_events = read_m5_sample(
        sales,
        b"d,date,wm_yr_wk,event_name_1\nd_1,2011-01-29,11101,\nd_2,2011-01-30,11101,Holiday\nd_3,2011-01-31,11102,\n",
        prices, max_series=2, max_days=2,
    )
    assert with_events.data.holiday.sum() == 2
    with pytest.raises(ValueError, match="calendar does not cover"):
        read_m5_sample(sales, b"d,date,wm_yr_wk\nd_1,2011-01-29,11101\n", prices)

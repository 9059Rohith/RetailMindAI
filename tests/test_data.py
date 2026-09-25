import pandas as pd
import pytest

from retailmind.data import assess_quality, clean_data, generate_retail_data, read_sales_csv


def test_generator_is_deterministic_and_retail_complete():
    first = generate_retail_data(products=3, stores=2, days=35, seed=7)
    second = generate_retail_data(products=3, stores=2, days=35, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 210
    assert {"revenue", "profit", "stockout", "promotion", "region", "lead_time"}.issubset(first)
    assert (first["units"] >= 0).all()


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
    cleaned, log = clean_data(bad)
    assert len(cleaned) < len(bad)
    assert (cleaned.stock >= 0).all()
    assert (cleaned.units >= 0).all()
    assert len(log) > 0
    assert bad.loc[1, "stock"] == -4


def test_bad_csv_gets_actionable_error():
    with pytest.raises(ValueError, match="Missing required columns"):
        read_sales_csv(b"date,units\n2025-01-01,2\n")

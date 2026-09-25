"""Guard the data-quality route against malformed user uploads."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from retailmind.data import read_m5_sample, read_sales_csv

APP = Path(__file__).resolve().parents[1] / "app" / "main.py"


def test_all_invalid_dates_reach_quality_review_without_crashing():
    app = AppTest.from_file(APP, default_timeout=120).run()
    app.session_state["dataset"] = read_sales_csv(
        b"date,product_id,store_id,units,price,stock\nnot-a-date,P1,S1,2,10,4\n"
    )
    app.radio[0].set_value("Data studio").run()

    assert not app.exception
    assert app.title[0].value == "Data studio"
    assert any("invalid dates" in warning.value for warning in app.warning)
    assert any(metric.label == "Health score" and metric.value == "0%" for metric in app.metric)


def test_demo_analytics_shows_holiday_and_seasonality_views():
    app = AppTest.from_file(APP, default_timeout=120).run()
    next(radio for radio in app.radio if radio.label == "Workspace").set_value("Analytics").run()
    assert not app.exception
    assert any(metric.label == "Monthly pattern" for metric in app.metric)
    assert any(metric.label == "Annual month-of-year pattern" for metric in app.metric)
    assert not any("Holiday labels are unavailable" in item.value for item in app.info)


def test_m5_mode_disables_inventory_without_fabricating_stock():
    sales = b"item_id,cat_id,store_id,state_id,d_1,d_2\nFOOD_1,FOODS,CA_1,CA,2,3\n"
    calendar = b"d,date,wm_yr_wk\nd_1,2011-01-29,11101\nd_2,2011-01-30,11101\n"
    prices = b"store_id,item_id,wm_yr_wk,sell_price\nCA_1,FOOD_1,11101,2.5\n"
    imported = read_m5_sample(sales, calendar, prices, 1, 2)
    app = AppTest.from_file(APP, default_timeout=120).run()
    app.session_state["dataset"] = imported.data
    app.session_state["mode"] = "m5"
    app.radio[0].set_value("Overview").run()
    assert not app.exception
    assert any("M5 benchmark mode" in item.value for item in app.info)
    assert any(metric.label == "Gross margin" and metric.value == "Unavailable" for metric in app.metric)
    app.radio[0].set_value("Analytics").run()
    assert not app.exception
    assert any("Holiday labels are unavailable" in item.value for item in app.info)
    next(radio for radio in app.radio if radio.label == "Workspace").set_value("Inventory").run()
    assert not app.exception
    assert any("Inventory planning and scenarios need observed stock" in item.value for item in app.warning)

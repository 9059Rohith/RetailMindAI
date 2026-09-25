"""Guard the data-quality route against malformed user uploads."""
from streamlit.testing.v1 import AppTest

from retailmind.data import read_sales_csv


def test_all_invalid_dates_reach_quality_review_without_crashing():
    app = AppTest.from_file("app/main.py", default_timeout=120).run()
    app.session_state["dataset"] = read_sales_csv(
        b"date,product_id,store_id,units,price,stock\nnot-a-date,P1,S1,2,10,4\n"
    )
    app.radio[0].set_value("Data studio").run()

    assert not app.exception
    assert app.title[0].value == "Data studio"
    assert any("invalid dates" in warning.value for warning in app.warning)
    assert any(metric.label == "Health score" and metric.value == "0%" for metric in app.metric)

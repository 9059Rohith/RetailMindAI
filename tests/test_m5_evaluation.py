import pandas as pd

from scripts.evaluate_m5 import evaluate_m5


def test_full_series_m5_baselines_hold_out_future_days(tmp_path):
    days = [f"d_{day}" for day in range(1, 71)]
    sales = pd.DataFrame([
        {"item_id": "A", "cat_id": "FOODS", "store_id": "CA_1", "state_id": "CA",
         **dict.fromkeys(days, 5)},
        {"item_id": "B", "cat_id": "HOBBIES", "store_id": "TX_1", "state_id": "TX",
         **{day: int(day[2:]) for day in days}},
    ])
    calendar = pd.DataFrame({"d": days, "date": pd.date_range("2025-01-01", periods=70),
                             "wm_yr_wk": 1})
    sales_path, calendar_path = tmp_path / "sales.csv", tmp_path / "calendar.csv"
    sales.to_csv(sales_path, index=False)
    calendar.to_csv(calendar_path, index=False)
    summary, sample = evaluate_m5(sales_path, calendar_path, horizon=7, history_days=63, sample_ml=0)
    assert summary["series"] == 2
    assert summary["holdout_start"] == "2025-03-05"
    assert summary["baselines_all_series"]["Naive"]["MAE"] > 0
    assert summary["baselines_all_series"]["Seasonal naive"]["MAE"] > 0
    assert sample.empty

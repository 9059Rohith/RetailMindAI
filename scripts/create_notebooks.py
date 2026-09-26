"""Build six small, reproducible research notebooks from the application modules."""
import json
from pathlib import Path


NOTEBOOKS = [
    ("01_data_understanding", "Data understanding", [
        "from pathlib import Path\nimport pandas as pd\nfrom retailmind.data import enrich, assess_quality\n",
        "data = enrich(pd.read_csv(Path('../data/m5_observed.csv.gz'), low_memory=False))\nprint(data.shape)\nprint(assess_quality(data))\ndata.head()\n",
    ]),
    ("02_eda", "Exploratory analysis", [
        "import pandas as pd\nimport plotly.express as px\nfrom retailmind.data import enrich\nfrom retailmind.analytics import daily_trend, dimension_summary, weekday_pattern\n",
        "data = enrich(pd.read_csv('../data/m5_observed.csv.gz', low_memory=False))\npx.line(daily_trend(data), x='date', y='units', title='Observed daily demand')\n",
        "dimension_summary(data, 'category')\nweekday_pattern(data)\n",
    ]),
    ("03_feature_engineering", "Leakage-safe features", [
        "import pandas as pd\nfrom retailmind.data import enrich\nfrom retailmind.forecast import daily_series, make_features\n",
        "data = enrich(pd.read_csv('../data/m5_observed.csv.gz', low_memory=False))\nseries = daily_series(data, data.product_id.iloc[0])\nfeatures = make_features(series)\nfeatures.tail()\n",
        "# The final row's demand-derived values depend on earlier rows only.\nassert features.iloc[-1].lag_1 == series.iloc[-2]\n",
    ]),
    ("04_forecasting", "Rolling-origin forecasting", [
        "import pandas as pd\nimport plotly.express as px\nfrom retailmind.data import enrich\nfrom retailmind.forecast import daily_series, run_forecast\n",
        "data = enrich(pd.read_csv('../data/m5_observed.csv.gz', low_memory=False))\nresult = run_forecast(daily_series(data, data.product_id.iloc[0]), horizon=14)\nresult.comparison.round(2)\n",
        "px.line(result.future, x='date', y=['forecast', 'lower', 'upper'], title='Forecast and heuristic range')\n",
    ]),
    ("05_inventory_analysis", "Inventory analysis", [
        "import pandas as pd\nfrom retailmind.data import enrich\nfrom retailmind.analytics import product_summary\nfrom retailmind.inventory import abc_xyz\n",
        "data = enrich(pd.read_csv('../data/m5_observed.csv.gz', low_memory=False))\nabc_xyz(product_summary(data))[['product', 'abc', 'xyz', 'segment']].head()\n",
        "# No observed stock or unit cost exists in M5, so replenishment must remain unavailable.\nassert data.stock.isna().all() and data.unit_cost.isna().all()\n",
    ]),
    ("06_model_comparison", "Model comparison and business consequences", [
        "import pandas as pd\nfrom retailmind.data import enrich\nfrom retailmind.forecast import backtest, daily_series\n",
        "data = enrich(pd.read_csv('../data/m5_observed.csv.gz', low_memory=False))\nresults = backtest(daily_series(data, data.product_id.iloc[0]), horizon=14)\nresults.groupby('model')[['WAPE', 'MAE', 'Bias', 'Underforecast', 'Overforecast']].mean().sort_values('WAPE').round(2)\n",
    ]),
]


def cell(source: str, kind: str = "code") -> dict:
    base = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        base.update({"execution_count": None, "outputs": []})
    return base


def main() -> None:
    output = Path("notebooks")
    output.mkdir(exist_ok=True)
    for slug, title, blocks in NOTEBOOKS:
        notebook = {"cells": [cell(f"# {title}\n\nRun from the `notebooks/` directory after installing `requirements.txt`. Outputs are calculated from the bundled observed M5 subset.", "markdown"),
                              cell("import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path.cwd().parent))\n")] + [cell(block) for block in blocks],
                    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.12"}},
                    "nbformat": 4, "nbformat_minor": 5}
        (output / f"{slug}.ipynb").write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(NOTEBOOKS)} notebooks to {output}")


if __name__ == "__main__":
    main()

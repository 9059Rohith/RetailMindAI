"""RetailMind AI Streamlit entry point."""
from __future__ import annotations

import hashlib
import html
import os
import sys
from pathlib import Path

# Allow the documented `streamlit run app/main.py` command from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.styles import CSS
from retailmind.analytics import (approximate_price_relationship, daily_trend, dimension_summary,
                                   kpis, product_summary, promotion_effect, weekday_pattern)
from retailmind.data import assess_quality, clean_data, enrich, generate_retail_data, read_sales_csv
from retailmind.database import database_engine, load_sales, save_sales
from retailmind.forecast import daily_series, explain_model, load_artifact, run_forecast, save_artifact
from retailmind.insights import build_insights
from retailmind.inventory import abc_xyz, allocate_limited_stock, plan_replenishment, scenario, stockout_trajectory

st.set_page_config(page_title="RetailMind AI · Retail intelligence", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

PLOT = {"paper_bgcolor": "#132239", "plot_bgcolor": "#132239", "font_color": "#c5d3e3", "margin": dict(l=28, r=24, t=44, b=28), "hoverlabel_bgcolor": "#1b324d"}
COLORS = ["#49d5db", "#a68af9", "#ffbf69", "#ff737d", "#8fbbff", "#60daa8"]


@st.cache_data(show_spinner=False)
def demo_data() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "data" / "demo_sales.csv"
    if path.exists():
        return enrich(pd.read_csv(path))
    return generate_retail_data(products=12, stores=4, days=120)


@st.cache_data(show_spinner=False)
def synthetic_data(products: int, stores: int, days: int, seed: int) -> pd.DataFrame:
    return generate_retail_data(products, stores, days, seed)


@st.cache_data(show_spinner=False)
def cached_plan(data: pd.DataFrame, service: float) -> pd.DataFrame:
    return plan_replenishment(data, service)


def chart(fig: go.Figure, height: int = 360) -> None:
    fig.update_layout(**PLOT, height=height, showlegend=True, legend=dict(orientation="h", y=-0.18))
    fig.update_xaxes(showgrid=False, linecolor="#35506d")
    fig.update_yaxes(gridcolor="#263b56", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def heading(title: str, subtitle: str) -> None:
    st.title(title)
    st.markdown(f'<p class="subtle">{subtitle}</p>', unsafe_allow_html=True)


def download_csv(label: str, frame: pd.DataFrame, filename: str) -> None:
    st.download_button(label, frame.to_csv(index=False).encode("utf-8"), filename, "text/csv", width="stretch")


def base_data() -> pd.DataFrame:
    return st.session_state.get("dataset", demo_data())


def filters(data: pd.DataFrame) -> pd.DataFrame:
    st.markdown("<div class='eyebrow'>Global filters</div>", unsafe_allow_html=True)
    cols = st.columns([1.7, 1, 1, 1, 1])
    minimum, maximum = pd.to_datetime(data.date).min().date(), pd.to_datetime(data.date).max().date()
    with cols[0]:
        dates = st.date_input("Date range", (minimum, maximum), min_value=minimum, max_value=maximum)
    with cols[1]:
        region = st.selectbox("Region", ["All regions"] + sorted(data.region.dropna().astype(str).unique().tolist()))
    regions = data if region == "All regions" else data[data.region.eq(region)]
    with cols[2]:
        store = st.selectbox("Store", ["All stores"] + sorted(regions.store.dropna().astype(str).unique().tolist()))
    with cols[3]:
        category = st.selectbox("Category", ["All categories"] + sorted(data.category.dropna().astype(str).unique().tolist()))
    categories = data if category == "All categories" else data[data.category.eq(category)]
    with cols[4]:
        product = st.selectbox("Product", ["All products"] + sorted(categories["product"].dropna().astype(str).unique().tolist()))
    selected = data.copy()
    if len(dates) == 2:
        selected = selected[selected.date.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
    if region != "All regions":
        selected = selected[selected.region.eq(region)]
    if store != "All stores":
        selected = selected[selected.store.eq(store)]
    if category != "All categories":
        selected = selected[selected.category.eq(category)]
    if product != "All products":
        selected = selected[selected["product"].eq(product)]
    return selected


def overview(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    values = kpis(data)
    at_risk = int(plan.risk.isin(["High", "Critical"]).sum()) if not plan.empty else 0
    for column, (label, value) in zip(st.columns(4), [("Revenue", f"₹{values['revenue']:,.0f}"), ("Units sold", f"{values['units']:,.0f}"), ("At-risk product-store pairs", f"{at_risk:,}"), ("Gross margin", f"{values['margin']:.1f}%")]):
        column.metric(label, value)
    left, right = st.columns([1.55, 1])
    with left:
        trend = daily_trend(data).tail(30)
        fig = px.bar(trend, x="date", y="revenue", title="Revenue trend · last 30 days", color_discrete_sequence=[COLORS[0]], labels={"revenue": "Revenue (₹)", "date": "Date"})
        chart(fig)
    with right:
        risk = plan.risk.value_counts().reindex(["Critical", "High", "Medium", "Low"], fill_value=0).reset_index()
        risk.columns = ["Risk", "Pairs"]
        fig = px.pie(risk, names="Risk", values="Pairs", hole=0.61, title="Inventory risk composition", color="Risk", color_discrete_map={"Critical": "#ff737d", "High": "#ffbf69", "Medium": "#a68af9", "Low": "#49d5db"})
        fig.update_traces(textinfo="none", marker_line_width=0)
        chart(fig)
    st.subheader("Top replenishment actions")
    if plan.empty:
        st.info("No inventory records match the selected filters.")
    else:
        display = plan[["product", "store", "stock", "days_cover", "recommended_order", "risk", "reason"]].head(10).copy()
        display.days_cover = display.days_cover.round(1)
        display.columns = ["Product", "Store", "Current stock", "Days of cover", "Recommended order", "Priority", "Reason"]
        st.dataframe(display, hide_index=True, width="stretch")


def data_studio(data: pd.DataFrame) -> None:
    upload, synth, database = st.tabs(["Upload & quality", "Synthetic data", "Database"])
    with upload:
        file = st.file_uploader("Upload a sales CSV", type="csv", help="Required: date, product_id, store_id, units, price, stock. Optional descriptive fields are filled explicitly.")
        if file and st.button("Load uploaded dataset", type="primary"):
            try:
                st.session_state.dataset = read_sales_csv(file.getvalue())
                st.session_state.source = file.name
                st.session_state.pop("forecast_result", None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        report = assess_quality(data)
        cols = st.columns(6)
        for col, (label, value) in zip(cols, [("Health score", f"{report.score}%"), ("Rows", f"{report.rows:,}"), ("Missing", f"{report.missing_pct:.2f}%"), ("Duplicates", report.duplicates), ("Invalid dates", report.invalid_dates), ("Outliers", report.outliers)]):
            col.metric(label, value)
        if report.issues:
            for issue in report.issues:
                st.warning(issue)
        else:
            st.success("No quality issues detected by the current rules.")
        cap = st.checkbox("Cap extreme unit outliers at the 99th percentile", value=False)
        if st.button("Auto clean dataset"):
            cleaned, log = clean_data(data, cap)
            st.session_state.original = data.copy()
            st.session_state.dataset = cleaned
            st.session_state.cleaning_log = log
            st.rerun()
        if "cleaning_log" in st.session_state:
            st.subheader("Cleaning report")
            st.dataframe(st.session_state.cleaning_log, hide_index=True, width="stretch")
            if st.button("Restore original dataset"):
                st.session_state.dataset = st.session_state.original
                st.session_state.pop("cleaning_log", None)
                st.rerun()
        st.dataframe(data.head(20), width="stretch", hide_index=True)
        download_csv("Download current dataset", data, "retailmind_sales.csv")
    with synth:
        st.write("Generate a seeded dataset with seasonality, promotions, holidays, suppliers, stockouts, returns and profit.")
        a, b, c, d = st.columns(4)
        products = a.number_input("Products", 50, 100, 54)
        stores = b.number_input("Stores", 10, 20, 12)
        days = c.number_input("Days", 90, 365, 180)
        seed = d.number_input("Random seed", 1, 99999, 42)
        if st.button("Generate dataset", type="primary"):
            with st.spinner("Generating retail records…"):
                st.session_state.dataset = synthetic_data(int(products), int(stores), int(days), int(seed))
                st.session_state.source = f"synthetic-{seed}"
                st.session_state.pop("forecast_result", None)
            st.rerun()
        if st.button("Restore included demo"):
            st.session_state.dataset = demo_data()
            st.session_state.source = "included demo"
            st.rerun()
    with database:
        st.write("SQLite works locally by default. Set DATABASE_MODE=mysql and credentials to use MySQL; connection failure falls back to SQLite.")
        if st.button("Save current dataset to database"):
            try:
                engine, mode = database_engine()
                save_sales(data, engine)
                st.success(f"Saved {len(data):,} rows to {mode}.")
            except Exception as exc:
                st.error(f"Database write failed: {exc}")
        if st.button("Load dataset from database"):
            try:
                engine, mode = database_engine()
                st.session_state.dataset = enrich(load_sales(engine))
                st.session_state.source = mode
                st.rerun()
            except Exception as exc:
                st.error(f"No saved dataset is available: {exc}")


def analytics(data: pd.DataFrame) -> None:
    values = kpis(data)
    cols = st.columns(5)
    for col, (label, value) in zip(cols, [("Revenue", f"₹{values['revenue']:,.0f}"), ("Gross profit", f"₹{values['profit']:,.0f}"), ("Units", f"{values['units']:,.0f}"), ("Average price", f"₹{values['average_price']:,.0f}"), ("Returns", f"{values['returns']:,.0f}")]):
        col.metric(label, value)
    trend_tab, product_tab, region_tab, signal_tab = st.tabs(["Sales trends", "Products & categories", "Stores & regions", "Demand signals"])
    with trend_tab:
        trend = daily_trend(data)
        metric = st.selectbox("Trend metric", ["revenue", "units", "profit"])
        chart(px.line(trend, x="date", y=metric, title=f"Daily {metric}", markers=False, color_discrete_sequence=[COLORS[0]]))
    with product_tab:
        summary = product_summary(data)
        st.dataframe(summary[["product", "category", "units", "revenue", "profit", "margin_pct", "demand_cv", "stock", "days_cover", "status"]].round(2), hide_index=True, width="stretch")
        category = dimension_summary(data, "category")
        chart(px.bar(category, x="category", y="revenue", color="category", title="Revenue by category", color_discrete_sequence=COLORS))
    with region_tab:
        choice = st.radio("Group by", ["store", "region"], horizontal=True)
        summary = dimension_summary(data, choice)
        chart(px.bar(summary, x=choice, y="revenue", color=choice, title=f"Revenue by {choice}", color_discrete_sequence=COLORS))
        st.dataframe(summary.round(2), hide_index=True, width="stretch")
    with signal_tab:
        a, b = st.columns(2)
        with a:
            chart(px.bar(weekday_pattern(data), x="weekday", y="mean_units", title="Mean units by weekday", color_discrete_sequence=[COLORS[0]]))
        with b:
            effect = promotion_effect(data)
            chart(px.bar(effect, x="promotion", y="mean_units", title="Promotion vs non-promotion observations", color="promotion", color_discrete_sequence=[COLORS[1], COLORS[0]]))
        relation = approximate_price_relationship(data)
        if pd.notna(relation["elasticity"]):
            st.info(f"Approximate log-price/log-demand association: {relation['elasticity']:.2f}. {relation['note']}.")
        else:
            st.info(str(relation["note"]))


def forecast_lab(data: pd.DataFrame) -> None:
    products = data[["product_id", "product"]].drop_duplicates().sort_values("product")
    names = dict(zip(products.product_id, products["product"]))
    a, b, c, d, e = st.columns(5)
    product_id = a.selectbox("Product", list(names), format_func=lambda key: names[key], key="forecast_product")
    stores = data[data.product_id.eq(product_id)][["store_id", "store"]].drop_duplicates()
    store_names = dict(zip(stores.store_id, stores.store))
    store = b.selectbox("Store", ["All stores"] + list(store_names), format_func=lambda key: store_names.get(key, key), key="forecast_store")
    horizon = c.slider("Forecast horizon (days)", 7, 30, 14)
    include_ml = d.checkbox("Include ML models", value=True)
    include_statistical = e.checkbox("Include ARIMA / SARIMA", value=False)
    try:
        series = daily_series(data, product_id, None if store == "All stores" else store)
    except ValueError as exc:
        st.warning(str(exc))
        return
    st.caption(f"{len(series)} daily observations · {series.index.min():%d %b %Y} to {series.index.max():%d %b %Y}. Future price, stock and promotions are excluded to prevent leakage.")
    if st.button("Train and compare models", type="primary"):
        try:
            with st.spinner("Running expanding-window backtests and generating future demand…"):
                result = run_forecast(series, horizon, include_ml, include_statistical)
            st.session_state.forecast_result = result
            st.session_state.forecast_key = (product_id, store, horizon, include_ml, include_statistical, len(series), float(series.sum()))
        except ValueError as exc:
            st.error(str(exc))
    key = (product_id, store, horizon, include_ml, include_statistical, len(series), float(series.sum()))
    if st.session_state.get("forecast_key") != key:
        st.info("Run model comparison to see a measured forecast for this selection.")
        return
    result = st.session_state.forecast_result
    winner = result.comparison.iloc[0]
    a, b, c, d = st.columns(4)
    a.metric("Selected model", result.winner)
    b.metric("Backtest WAPE", f"{winner.WAPE:.1f}%")
    c.metric("Forecast units", f"{result.future.forecast.sum():,.0f}")
    d.metric("Mean bias", f"{winner.Bias:+.1f} units/day")
    fig = go.Figure()
    history = result.history.tail(60)
    future = result.future
    fig.add_trace(go.Scatter(x=history.date, y=history.units, name="Observed", line=dict(color="#8fbbff")))
    fig.add_trace(go.Scatter(x=future.date, y=future.upper, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=future.date, y=future.lower, mode="lines", fill="tonexty", fillcolor="rgba(73,213,219,.18)", line=dict(width=0), name="Heuristic uncertainty band"))
    fig.add_trace(go.Scatter(x=future.date, y=future.forecast, name="Forecast", line=dict(color="#49d5db", width=3)))
    fig.update_layout(title="Observed demand and forecast", yaxis_title="Units/day")
    chart(fig, 430)
    st.caption("The shaded range uses backtest MAE as a heuristic width; it is not a statistically calibrated 90% prediction interval.")
    st.subheader("Model comparison · mean across expanding-window folds")
    st.dataframe(result.comparison.round(2), hide_index=True, width="stretch")
    with st.expander("Why this model?", expanded=False):
        st.write(f"{result.winner} had the lowest mean held-out WAPE (MAE breaks ties) across expanding-window folds. This selects a model by measured historical errors, not by a claim that it will always win in future periods.")
        if result.winner in {"Random forest", "Gradient boosting"}:
            importance = explain_model(series, result.winner).head(8)
            st.caption("Permutation importance on recent training observations. It shows predictive association, not causal influence.")
            chart(px.bar(importance, x="importance", y="feature", orientation="h", title="Top historical features", color_discrete_sequence=[COLORS[0]]), 330)
        else:
            explanations = {"Naive": "Repeats the latest observed day.", "Seasonal naive": "Repeats the last seven-day pattern.",
                            "Moving average": "Uses the mean of the latest 28 days.", "Exponential smoothing": "Weights recent observations more strongly.",
                            "ARIMA": "Uses autoregressive and moving-average structure.", "SARIMA": "Adds a seven-day seasonal autoregressive term."}
            st.info(explanations.get(result.winner, "The model extrapolates past demand patterns."))
    download_csv("Download forecast", result.future, "forecast.csv")
    if st.button("Save model run metadata"):
        version = hashlib.sha256(pd.util.hash_pandas_object(data, index=False).values.tobytes()).hexdigest()[:12]
        target = save_artifact(result, Path(os.getenv("MODEL_PATH", "artifacts")) / "latest_forecast.joblib", version)
        st.success(f"Saved forecast, features, metrics and dataset version to {target}.")
    path = Path(os.getenv("MODEL_PATH", "artifacts")) / "latest_forecast.joblib"
    if path.exists() and st.button("Load existing model run"):
        try:
            artifact = load_artifact(path)
            st.info(f"Saved run: {artifact['winner']} · {artifact['trained_at']} · dataset {artifact['dataset_version']}")
            st.dataframe(artifact["future"], hide_index=True, width="stretch")
        except Exception as exc:
            st.error(f"Could not load artifact: {exc}")


def inventory_page(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    if plan.empty:
        st.info("No inventory records match your filters.")
        return
    a, b, c, d = st.columns(4)
    a.metric("Critical", int(plan.risk.eq("Critical").sum()))
    b.metric("High risk", int(plan.risk.eq("High").sum()))
    c.metric("Suggested units", f"{plan.recommended_order.sum():,}")
    d.metric("Excess cover", int(plan.days_cover.gt(60).sum()))
    planner, segments, simulator, allocation = st.tabs(["Replenishment planner", "ABC × XYZ", "Stockout simulator", "Limited allocation"])
    with planner:
        st.caption("Safety stock = z × daily demand standard deviation × √lead time. Reorder point = mean lead-time demand + safety stock. EOQ assumes fixed order and annual holding costs.")
        shown = plan[["product", "store", "stock", "daily_mean", "days_cover", "lead_time", "safety_stock", "reorder_point", "eoq", "recommended_order", "risk", "reason"]].copy()
        shown.columns = ["Product", "Store", "Current stock", "Daily demand", "Days of cover", "Lead time", "Safety stock", "Reorder point", "EOQ", "Order units", "Risk", "Reason"]
        st.dataframe(shown.round(1), hide_index=True, width="stretch")
        download_csv("Download recommendations", plan, "replenishment.csv")
    with segments:
        segments = abc_xyz(product_summary(data))
        st.dataframe(segments[["product", "revenue", "demand_cv", "abc", "xyz", "segment", "status"]].round(2), hide_index=True, width="stretch")
        matrix = segments.pivot_table(index="abc", columns="xyz", values="product_id", aggfunc="count", fill_value=0).reindex(index=["A", "B", "C"], columns=["X", "Y", "Z"], fill_value=0)
        chart(px.imshow(matrix, text_auto=True, color_continuous_scale=[[0,"#172941"],[1,"#49d5db"]], title="Product count by value and volatility", labels={"x":"Demand variability", "y":"Revenue class"}))
    with simulator:
        choices = plan.head(100).copy()
        labels = choices.apply(lambda row: f"{row['product']} · {row['store']}", axis=1).tolist()
        selected = choices.iloc[st.selectbox("Product and store", range(len(labels)), format_func=lambda i: labels[i])]
        c1, c2, c3 = st.columns(3)
        stock = c1.number_input("Current stock", 0, 100000, int(selected.stock))
        lead = c2.number_input("Incoming order day", 1, 90, int(selected.lead_time))
        incoming = c3.number_input("Incoming quantity", 0, 100000, int(selected.recommended_order))
        projection = stockout_trajectory(stock, np.repeat(selected.daily_mean, 30), lead, incoming)
        zero = projection[projection.projected_stock.le(0)]
        st.metric("Projected stockout", f"Day {int(zero.day.iloc[0])}" if not zero.empty else "Beyond 30 days")
        chart(px.line(projection, x="day", y="projected_stock", markers=True, title="Projected inventory after expected demand", labels={"day":"Days ahead", "projected_stock":"Units on hand"}, color_discrete_sequence=[COLORS[0]]))
    with allocation:
        chosen = st.selectbox("Allocate a product", sorted(data["product"].unique()))
        eligible = plan[plan["product"].eq(chosen)].copy()
        requests = pd.DataFrame({"store": eligible.store, "demand": np.ceil(eligible.daily_mean * eligible.lead_time + eligible.safety_stock).astype(int), "priority": np.maximum(1, eligible.risk_score)})
        total = int(requests.demand.sum())
        available = st.number_input("Available units at distribution center", 0, max(1, total * 2), max(1, total // 2))
        result = allocate_limited_stock(requests, int(available))
        st.caption("Linear optimization maximizes priority-weighted fulfilled demand under a shared stock cap. Ties are resolved by store order.")
        st.dataframe(result, hide_index=True, width="stretch")
        st.metric("Unmet demand after allocation", f"{result.unmet.sum():,} units")


def scenarios(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    if plan.empty:
        st.info("No product-store pairs match your filters.")
        return
    labels = plan.apply(lambda row: f"{row['product']} · {row['store']}", axis=1).tolist()
    row = plan.iloc[st.selectbox("Product and store", range(len(plan)), format_func=lambda i: labels[i])]
    subset = data[data.product_id.eq(row.product_id) & data.store_id.eq(row.store_id)]
    a, b, c = st.columns(3)
    price = a.number_input("Base price (₹)", min_value=0.01, value=float(subset.price.mean()), step=1.0)
    cost = b.number_input("Unit cost (₹)", min_value=0.0, value=float(subset.unit_cost.mean()), step=1.0)
    horizon = c.slider("Horizon (days)", 7, 60, 30)
    a, b, c, d = st.columns(4)
    discount = a.slider("Discount (%)", 0, 50, 10)
    promotion = b.toggle("Promotion active", value=True)
    lead = c.number_input("Supplier lead time (days)", 1, 90, int(row.lead_time))
    stock = d.number_input("Current stock", 0, 100000, int(row.stock))
    order = st.slider("Order quantity", 0, max(100, int(row.recommended_order * 3)), int(row.recommended_order))
    common = dict(base_daily_demand=float(row.daily_mean), price=price, unit_cost=cost, stock=stock, lead_time=int(lead), horizon=horizon)
    baseline = scenario(**common)
    changed = scenario(**common, discount_pct=discount / 100, promotion=promotion, order_qty=order)
    comparison = pd.DataFrame([{"scenario": "Baseline", **baseline}, {"scenario": "Proposed", **changed}])
    comparison_display = comparison.T.reset_index().astype(str)
    comparison_display.columns = ["Metric", "Baseline", "Proposed"]
    st.dataframe(comparison_display, hide_index=True, width="stretch")
    a, b, c = st.columns(3)
    a.metric("Demand change", f"{changed['projected_demand']-baseline['projected_demand']:+,.0f} units")
    b.metric("Revenue change", f"₹{changed['revenue']-baseline['revenue']:+,.0f}")
    c.metric("Gross profit change", f"₹{changed['gross_profit']-baseline['gross_profit']:+,.0f}")
    chart(px.bar(comparison, x="scenario", y=["projected_demand", "fulfilled_units", "unmet_demand"], barmode="group", title="Demand, fulfilled units and missed demand", color_discrete_sequence=COLORS))
    st.warning("Simulation uses an assumed price elasticity of −1.1 and a 15% promotion uplift. These are scenarios, not causal estimates or measured ROI.")
    download_csv("Download scenario comparison", comparison, "scenarios.csv")


def insights_page(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    insights = build_insights(data, plan)
    for item in insights:
        st.markdown(f'<div class="insight"><small>{html.escape(item["level"].upper())} · {html.escape(item["basis"])}</small><br><b>{html.escape(item["title"])}</b><p>{html.escape(item["detail"])}</p></div>', unsafe_allow_html=True)
    download_csv("Download alerts", pd.DataFrame(insights), "insights.csv")


def reports(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    summary = pd.DataFrame([kpis(data)])
    insights = pd.DataFrame(build_insights(data, plan))
    a, b, c = st.columns(3)
    with a:
        download_csv("Sales dataset · CSV", data, "sales.csv")
    with b:
        download_csv("KPI summary · CSV", summary, "kpis.csv")
    with c:
        download_csv("Recommendations · CSV", plan, "inventory_recommendations.csv")
    if not insights.empty:
        download_csv("Insights & alerts · CSV", insights, "alerts.csv")
    if "forecast_result" in st.session_state:
        download_csv("Latest forecast · CSV", st.session_state.forecast_result.future, "forecast.csv")
        download_csv("Model metrics · CSV", st.session_state.forecast_result.comparison, "model_metrics.csv")
    st.subheader("Current dataset profile")
    report = assess_quality(data)
    st.json({"source": st.session_state.get("source", "included demo"), "rows": report.rows, "columns": report.columns,
             "date_start": str(data.date.min().date()), "date_end": str(data.date.max().date()), "health_score": report.score,
             "products": int(data.product_id.nunique()), "stores": int(data.store_id.nunique())})


def main() -> None:
    with st.sidebar:
        st.markdown('<div class="brand">▥ RetailMind <span>AI</span></div><div class="brand-sub">Turn retail data into action</div>', unsafe_allow_html=True)
        page = st.radio("Workspace", ["Overview", "Data studio", "Analytics", "Forecast lab", "Inventory", "Scenarios", "Insights", "Reports"], label_visibility="collapsed")
        st.divider()
        st.caption(f"SOURCE · {st.session_state.get('source', 'included demo').upper()}")
        st.caption("Deterministic demo data · no paid API")
    all_data = base_data()
    titles = {"Overview": ("Retail intelligence, in one view", "From sales signals to confident inventory decisions."),
              "Data studio": ("Data studio", "Bring in a dataset, inspect its health, and document every cleaning step."),
              "Analytics": ("Business analytics", "Understand observed sales by time, product, store and region."),
              "Forecast lab": ("Forecast lab", "Compare models with rolling-origin tests before trusting a demand forecast."),
              "Inventory": ("Inventory intelligence", "Prioritize stock risk and turn demand variability into replenishment quantities."),
              "Scenarios": ("What-if scenarios", "Change operating assumptions and see the simulated inventory and margin outcome."),
              "Insights": ("Insights & alerts", "Evidence-backed signals with a clear distinction between observation and recommendation."),
              "Reports": ("Reports", "Export the evidence behind your retail decisions.")}
    heading(*titles[page])
    filtered = filters(all_data)
    if filtered.empty and page != "Data studio":
        st.warning("No records match the selected filters. Broaden the date or entity selection.")
        return
    plan = cached_plan(filtered, 0.95)
    pages = {"Overview": overview, "Data studio": data_studio, "Analytics": analytics, "Forecast lab": forecast_lab,
             "Inventory": inventory_page, "Scenarios": scenarios, "Insights": insights_page, "Reports": reports}
    page_slot = st.empty()
    with page_slot.container():
        if page in {"Overview", "Inventory", "Scenarios", "Insights", "Reports"}:
            pages[page](filtered, plan)
        else:
            pages[page](all_data if page == "Data studio" else filtered)
    st.markdown('<p class="footer-note">RetailMind AI · Observations, forecasts and simulations are labeled separately. Inventory recommendations require business review.</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()

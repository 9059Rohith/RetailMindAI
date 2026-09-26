"""RetailMind AI Streamlit entry point."""
from __future__ import annotations

import html
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow the documented `streamlit run app/main.py` command from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.styles import CSS
from retailmind.analytics import (approximate_price_relationship, daily_trend, demand_signals,
                                   dimension_summary, holiday_effect, kpis, product_summary,
                                   promotion_effect, weekday_pattern)
from retailmind.data import assess_quality, clean_data, dataset_metadata, enrich, read_m5_sample, read_sales_csv
from retailmind.database import database_engine, load_sales, save_sales
from retailmind.forecast import (daily_series, explain_model, explain_next_day, list_artifacts, load_artifact,
                                 register_artifact, run_forecast)
from retailmind.insights import build_insights
from retailmind.inventory import (RiskSettings, abc_xyz, allocate_limited_stock,
                                   plan_replenishment, scenario, stockout_trajectory)

st.set_page_config(page_title="RetailMind AI · Retail intelligence", page_icon="◈", layout="wide", initial_sidebar_state="auto")
st.markdown(CSS, unsafe_allow_html=True)

PLOT = {"paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)", "font_color": "#bbcade", "margin": dict(l=26, r=26, t=64, b=40), "hoverlabel_bgcolor": "#152841"}
COLORS = ["#49d5db", "#a68af9", "#ffbf69", "#ff737d", "#8fbbff", "#60daa8"]


@st.cache_data(show_spinner=False)
def observed_data() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "data" / "m5_observed.csv.gz"
    return enrich(pd.read_csv(path, compression="gzip", low_memory=False))


@st.cache_data(show_spinner=False)
def cached_plan(data: pd.DataFrame, service: float, policy: RiskSettings,
                forecast_errors: dict[tuple[str, str], float]) -> pd.DataFrame:
    return plan_replenishment(data, service, risk_settings=policy, forecast_error_rates=forecast_errors)


@st.cache_data(show_spinner=False)
def cached_explanations(series: pd.Series, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return explain_model(series, model), explain_next_day(series, model)


def chart(fig: go.Figure, height: int = 360) -> None:
    fig.update_layout(**PLOT, height=height, showlegend=True,
                      font=dict(family="DM Sans, sans-serif", size=12, color="#bbcade"),
                      title=dict(font=dict(family="Manrope, sans-serif", size=17, color="#f1f8ff"), x=.04, y=.95),
                      legend=dict(orientation="h", y=-.21, x=0, font=dict(size=11)),
                      hovermode="x unified", hoverlabel=dict(bgcolor="#172b43", font_size=12))
    fig.update_xaxes(showgrid=False, linecolor="#31455e", tickfont=dict(color="#8fa6be"), title_font=dict(color="#a8bfd5"))
    fig.update_yaxes(gridcolor="rgba(117,151,186,.12)", linecolor="#31455e", zeroline=False,
                     tickfont=dict(color="#8fa6be"), title_font=dict(color="#a8bfd5"))
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def heading(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="page-heading"><span class="eyebrow">RETAILMIND / WORKSPACE</span><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>', unsafe_allow_html=True)


def currency_symbol() -> str:
    return "$" if st.session_state.get("mode", "m5") == "m5" else st.session_state.get("currency", "")


def download_csv(label: str, frame: pd.DataFrame, filename: str) -> None:
    st.download_button(label, frame.to_csv(index=False).encode("utf-8"), filename, "text/csv", width="stretch")


def base_data() -> pd.DataFrame:
    return st.session_state.get("dataset", observed_data())


def current_risk_settings() -> RiskSettings:
    return RiskSettings(st.session_state.get("dead_stock_days", 30), st.session_state.get("excess_cover_days", 60),
                        st.session_state.get("volatility_points", 8), st.session_state.get("stockout_points", 10),
                        st.session_state.get("forecast_error_points", 10))


def activate_dataset(data: pd.DataFrame, source: str, mode: str) -> None:
    st.session_state.dataset = data
    st.session_state.source = source
    st.session_state.mode = mode
    st.session_state.dataset_created_at = datetime.now(timezone.utc).isoformat()
    st.session_state.pop("forecast_result", None)
    st.session_state.pop("forecast_key", None)
    st.session_state.pop("forecast_error_rates", None)


def filters(data: pd.DataFrame) -> pd.DataFrame:
    st.markdown("<div class='eyebrow'>Global filters</div>", unsafe_allow_html=True)
    has_promotion = data.promotion.notna().any()
    cols = st.columns([1.7, 1, 1, 1, 1] + ([1] if has_promotion else []))
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
    promotion = "All sales"
    if has_promotion:
        with cols[5]:
            promotion = st.selectbox("Promotion", ["All sales", "Promoted", "Non-promoted"])
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
    if promotion != "All sales":
        selected = selected[selected.promotion.eq(promotion == "Promoted")]
    return selected


def _sparkline(values: pd.Series) -> str:
    points = values.tail(28).to_numpy(dtype=float)
    if not len(points):
        return ""
    spread = max(float(points.max() - points.min()), 1.0)
    coordinates = " ".join(f"{i * 380 / max(len(points) - 1, 1):.1f},{106 - (value - points.min()) / spread * 78:.1f}" for i, value in enumerate(points))
    return (f'<svg viewBox="0 0 380 120" preserveAspectRatio="none" role="img" aria-label="Observed units over the last 28 days">'
            f'<defs><linearGradient id="pulse-fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#59e0d4" stop-opacity=".32"/><stop offset="1" stop-color="#59e0d4" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="0,120 {coordinates} 380,120" fill="url(#pulse-fill)"/><polyline points="{coordinates}" fill="none" stroke="#66e8df" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/></svg>')


def overview(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    values = kpis(data)
    currency = currency_symbol()
    total = len(data)
    priced = int(data.price.notna().sum())
    coverage = priced / total * 100
    daily = daily_trend(data).sort_values("date")
    recent_days = min(28, len(daily))
    recent = float(daily.units.tail(recent_days).sum())
    previous = float(daily.units.iloc[-56:-28].sum()) if len(daily) >= 56 else np.nan
    change = (recent / previous - 1) * 100 if previous and np.isfinite(previous) else np.nan
    change_label = f"{change:+.1f}%" if np.isfinite(change) else "Unavailable"
    pairs = data.groupby(["product_id", "store_id"]).ngroups
    observed_days = (data.date.max() - data.date.min()).days + 1
    source_label = "HISTORICAL M5" if st.session_state.get("mode", "m5") == "m5" else "UPLOADED RETAIL DATA"
    outlook_label = "archival outlook" if source_label == "HISTORICAL M5" else "seasonal outlook"
    st.markdown(
        f'<section class="command-hero"><div class="command-hero__copy"><div class="hero-status"><span class="status-pulse"></span> OBSERVED RETAIL RECORDS <span class="hero-status__sep">/</span> {source_label}</div>'
        f'<h1>Every sale is<br><em>a signal.</em></h1><p>Explore what sold, where demand shifted, and how forecasting models perform on observed retail history.</p>'
        f'<div class="hero-chips"><span>◈ {data.product_id.nunique():,} products</span><span>⌑ {data.store_id.nunique():,} stores</span><span>▤ {total:,} observations</span></div></div>'
        f'<div class="hero-visual"><div class="hero-visual__top"><span>OBSERVED MOMENTUM</span><span>{data.date.max():%d %b %Y}</span></div>'
        f'<div class="hero-visual__value">{recent:,.0f}<small>units / latest {recent_days} observed days</small></div><div class="hero-visual__spark">{_sparkline(daily.units)}</div>'
        f'<div class="hero-visual__foot"><span>28-day change <strong>{change_label}</strong></span><span>{observed_days:,}-day selected window</span></div></div></section>',
        unsafe_allow_html=True)
    revenue = f"{currency}{values['revenue']:,.0f}" if np.isfinite(values["revenue"]) else "Unavailable"
    metrics = [
        ("01", "Observed revenue", revenue, f"{coverage:.1f}% of rows have a price", "teal", coverage),
        ("02", "Units sold", f"{values['units']:,.0f}", "Measured across the selected records", "blue", 100),
        ("03", "Demand movement", change_label, "Latest 28 days vs prior 28 days", "violet", min(abs(change), 100) if np.isfinite(change) else 0),
        ("04", "Active series", f"{pairs:,}", "Product / store combinations", "amber", 100),
    ]
    cards = "".join(f'<div class="signal-card signal-card--{tone}"><div class="signal-card__top"><span>{index} / {html.escape(label)}</span><span class="signal-card__dot"></span></div>'
                    f'<strong>{html.escape(value)}</strong><small>{html.escape(context)}</small><div class="signal-card__track"><i style="width:{bar:.1f}%"></i></div></div>'
                    for index, label, value, context, tone, bar in metrics)
    st.markdown(f'<div class="signal-grid">{cards}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-head"><span>01 / SALES PULSE</span><h2>Observed pattern & {outlook_label}</h2><p>Actual sold units are shown beside a transparent seven-day seasonal baseline.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.5, 1])
    with left:
        shown = daily.tail(90).copy()
        shown["seven_day_average"] = shown.units.rolling(7, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=shown.date, y=shown.units, mode="lines", name="Observed", line=dict(color="rgba(105,188,208,.45)", width=1.5), hovertemplate="%{x|%d %b %Y}<br>%{y:,.0f} units<extra></extra>"))
        fig.add_trace(go.Scatter(x=shown.date, y=shown.seven_day_average, mode="lines", name="7-day average", line=dict(color=COLORS[0], width=3), fill="tozeroy", fillcolor="rgba(73,213,219,.07)", hovertemplate="%{x|%d %b %Y}<br>%{y:,.1f} units<extra></extra>"))
        fig.update_layout(title="Sales velocity · last 90 observed days", yaxis_title="Units sold", xaxis_title="")
        chart(fig, 370)
    with right:
        if len(daily) >= 7:
            horizon = 14
            outlook = pd.DataFrame({"date": pd.date_range(start=daily.date.iloc[-1], periods=horizon + 1, freq="D")[1:],
                                    "units": np.resize(daily.units.tail(7).to_numpy(dtype=float), horizon)})
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=daily.date.tail(28), y=daily.units.tail(28), name="Observed", line=dict(color=COLORS[4], width=2)))
            fig.add_trace(go.Scatter(x=outlook.date, y=outlook.units, name="Seasonal baseline", line=dict(color=COLORS[1], width=3, dash="dot")))
            fig.update_layout(title=f"{horizon}-day seasonal baseline", yaxis_title="Units / day", xaxis_title="")
            chart(fig, 370)
            st.caption("The baseline repeats the last seven observed days. Compare measured models and held-out errors in Forecast lab.")
    st.markdown('<div class="section-head"><span>02 / MIX & SIGNALS</span><h2>Where the volume came from</h2><p>Category mix and evidence based observations update with your filters.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.15, 1])
    with left:
        category = dimension_summary(data, "category").sort_values("units")
        if category.empty:
            st.info("Category labels are unavailable.")
        else:
            fig = go.Figure(go.Bar(x=category.units, y=category.category, orientation="h", marker_color=[COLORS[4], COLORS[1], COLORS[0]] * (len(category) // 3 + 1),
                                   text=category.units.map(lambda number: f"{number:,.0f}"), textposition="outside"))
            fig.update_layout(title="Unit sales by category", xaxis_title="Observed units", yaxis_title="", showlegend=False)
            chart(fig, 315)
    with right:
        evidence = []
        if not category.empty:
            top = category.iloc[-1]
            share = f"{top.units / values['units'] * 100:.1f}% of selected sales" if values["units"] else "Share unavailable when selected sales are zero"
            evidence.append(("CATEGORY LEADER", str(top.category), f"{top.units:,.0f} units · {share}"))
        peak = daily.tail(90).sort_values("units", ascending=False).iloc[0]
        evidence.append(("PEAK OBSERVED DAY", f"{peak.date:%d %b %Y}", f"{peak.units:,.0f} units sold across the selected records"))
        for item in build_insights(data, plan, current_risk_settings())[:1]:
            evidence.append((item["basis"].upper(), item["title"], item["detail"]))
        if plan.empty:
            evidence.append(("DATA LIMITATION", "Inventory unavailable", "M5 has no observed stock, cost or lead time. No reorder quantity is produced."))
        content = "".join(f'<div class="evidence-row"><span>{html.escape(label)}</span><strong>{html.escape(title)}</strong><p>{html.escape(detail)}</p></div>' for label, title, detail in evidence)
        st.markdown(f'<div class="evidence-panel"><div class="evidence-panel__head">EVIDENCE DESK <span>{len(evidence):02d} SIGNALS</span></div>{content}</div>', unsafe_allow_html=True)


def data_studio(data: pd.DataFrame) -> None:
    upload, benchmark, database = st.tabs(["Quality & lineage", "Import official M5", "Database"])
    with upload:
        st.caption("The bundled source contains observed M5 product/store/day sales, weekly prices, and calendar events. Missing prices remain missing.")
        file = st.file_uploader("Upload an observed sales CSV", type="csv", help="Required: date, product_id, store_id, units. Optional price, stock, cost and descriptive fields remain missing when absent.")
        if file and st.button("Load uploaded dataset", type="primary"):
            try:
                activate_dataset(read_sales_csv(file.getvalue()), file.name, "retail")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        report = assess_quality(data)
        cols = st.columns(6)
        for col, (label, value) in zip(cols, [("Health score", f"{report.score}%"), ("Rows", f"{report.rows:,}"), ("Missing required", f"{report.missing_pct:.2f}%"), ("Duplicates", report.duplicates), ("Invalid dates", report.invalid_dates), ("Outliers", report.outliers)]):
            col.metric(label, value)
        if report.issues:
            for issue in report.issues:
                st.warning(issue)
        else:
            st.success("No quality issues detected by the current rules.")
        st.subheader("Data health checks")
        st.dataframe(pd.DataFrame([check.__dict__ for check in report.checks]), hide_index=True, width="stretch")
        availability = pd.DataFrame({"field": ["price", "stock", "unit_cost", "lead_time", "promotion", "holiday"],
                                     "observed_rows": [int(data[col].notna().sum()) if col in data else 0 for col in ("price", "stock", "unit_cost", "lead_time", "promotion", "holiday")]})
        st.subheader("Field availability")
        st.dataframe(availability, hide_index=True, width="stretch")
        if st.button("Quarantine invalid rows"):
            cleaned, log = clean_data(data)
            st.session_state.original = data.copy()
            activate_dataset(cleaned, st.session_state.get("source", "M5 observed sample") + " · cleaned", st.session_state.get("mode", "m5"))
            st.session_state.cleaning_log = log
            st.rerun()
        if "cleaning_log" in st.session_state:
            st.subheader("Cleaning report")
            st.dataframe(st.session_state.cleaning_log, hide_index=True, width="stretch")
            if st.button("Restore original dataset"):
                activate_dataset(st.session_state.original, st.session_state.get("source", "M5 observed sample").replace(" · cleaned", ""), st.session_state.get("mode", "m5"))
                st.session_state.pop("cleaning_log", None)
                st.rerun()
        st.dataframe(data.head(20), width="stretch", hide_index=True)
        st.json(dataset_metadata(data, st.session_state.get("source", "M5 observed sample"),
                                  st.session_state.get("dataset_created_at")))
        download_csv("Download current dataset", data, "retailmind_sales.csv")
        if st.button("Restore bundled M5 observations"):
            activate_dataset(observed_data(), "M5 observed sample", "m5")
            st.rerun()
    with benchmark:
        st.write("Import official M5 wide sales, calendar and weekly price files. The bundled observed sample is ready without uploading anything.")
        m5_sales = st.file_uploader("M5 sales_train_evaluation.csv", type="csv", key="m5_sales")
        m5_calendar = st.file_uploader("M5 calendar.csv", type="csv", key="m5_calendar")
        m5_prices = st.file_uploader("M5 sell_prices.csv", type="csv", key="m5_prices")
        a, b = st.columns(2)
        series_limit = a.number_input("M5 product-store series", 1, 100, 24)
        day_limit = b.number_input("Recent M5 days", 35, 365, 180)
        if st.button("Import M5 sample", type="primary"):
            if not all((m5_sales, m5_calendar, m5_prices)):
                st.error("Upload all three official M5 CSVs before importing.")
            else:
                try:
                    imported = read_m5_sample(m5_sales, m5_calendar, m5_prices,
                                              int(series_limit), int(day_limit))
                    activate_dataset(imported.data, "M5 benchmark sample", "m5")
                    st.session_state.m5_missing_prices = imported.missing_prices
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.caption("M5 has no stock or unit cost. Inventory orders and gross profit are unavailable without retailer records.")
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
                loaded = enrich(load_sales(engine))
                activate_dataset(loaded, mode, "m5" if loaded.stock.isna().all() else "retail")
                st.rerun()
            except Exception as exc:
                st.error(f"No saved dataset is available: {exc}")


def analytics(data: pd.DataFrame) -> None:
    values = kpis(data)
    currency = currency_symbol()
    displayed = [("Units sold", f"{values['units']:,.0f}"), ("Product / store pairs", f"{data.groupby(['product_id','store_id']).ngroups:,}")]
    if np.isfinite(values["revenue"]):
        displayed.insert(0, ("Observed revenue", f"{currency}{values['revenue']:,.0f}"))
        displayed.append(("Average observed selling price", f"{currency}{values['average_price']:,.2f}"))
    if np.isfinite(values["profit"]):
        displayed.append(("Gross profit", f"{currency}{values['profit']:,.0f}"))
    if np.isfinite(values["returns"]):
        displayed.append(("Recorded returns", f"{values['returns']:,.0f}"))
    cols = st.columns(len(displayed))
    for col, (label, value) in zip(cols, displayed):
        col.metric(label, value)
    if data.price.isna().any():
        st.caption(f"Revenue includes {data.price.notna().sum():,} priced observations; {data.price.isna().sum():,} unpriced observations are excluded, not valued at zero.")
    trend_tab, product_tab, region_tab, signal_tab = st.tabs(["Sales trends", "Products & categories", "Stores & regions", "Demand signals"])
    with trend_tab:
        trend = daily_trend(data)
        choices = ["units"] + (["revenue"] if data.price.notna().any() else []) + (["profit"] if data.unit_cost.notna().any() else [])
        metric = st.selectbox("Trend metric", choices)
        chart(px.line(trend, x="date", y=metric, title=f"Daily {metric}", markers=False, color_discrete_sequence=[COLORS[0]]))
    with product_tab:
        summary = product_summary(data)
        columns = ["product", "category", "units", "demand_cv", "days_since_sale"]
        if data.price.notna().any():
            columns += ["revenue"]
        if data.unit_cost.notna().any():
            columns += ["profit", "margin_pct"]
        if data.stock.notna().any():
            columns += ["stock", "days_cover", "status"]
        st.dataframe(summary[columns].round(2), hide_index=True, width="stretch")
        category = dimension_summary(data, "category")
        chart(px.bar(category, x="category", y="units", color="category", title="Observed demand by category", color_discrete_sequence=COLORS))
    with region_tab:
        choice = st.radio("Group by", ["store", "region"], horizontal=True)
        summary = dimension_summary(data, choice)
        chart(px.bar(summary, x=choice, y="units", color=choice, title=f"Observed units by {choice}", color_discrete_sequence=COLORS))
        visible = [choice, "units"] + (["revenue"] if data.price.notna().any() else []) + (["latest_stock"] if data.stock.notna().any() else [])
        st.dataframe(summary[visible].round(2), hide_index=True, width="stretch")
        if {"latitude", "longitude"}.issubset(data.columns):
            locations = data.sort_values("date").drop_duplicates("store_id", keep="last")
            locations = locations.dropna(subset=["latitude", "longitude"])
            if not locations.empty:
                totals = data.groupby("store_id", as_index=False)["revenue"].sum()
                locations = locations.merge(totals, on="store_id", suffixes=("", "_total"))
                chart(px.scatter_geo(locations, lat="latitude", lon="longitude", size="revenue_total",
                                     hover_name="store", color="region", title="Store locations and observed revenue"), 420)
    with signal_tab:
        a, b = st.columns(2)
        with a:
            chart(px.bar(weekday_pattern(data), x="weekday", y="mean_units", title="Mean units by weekday", color_discrete_sequence=[COLORS[0]]))
        with b:
            if data.promotion.notna().any():
                effect = promotion_effect(data)
                chart(px.bar(effect, x="promotion", y="mean_units", title="Observed demand by promotion label", color="promotion", color_discrete_sequence=[COLORS[1], COLORS[0]]))
            else:
                st.info("Promotion labels are unavailable in this dataset.")
        holidays = holiday_effect(data)
        if holidays.empty:
            st.info("Holiday labels are unavailable for this dataset.")
        else:
            chart(px.bar(holidays, x="holiday", y="mean_units", color="holiday",
                         title="Holiday vs ordinary observations",
                         labels={"holiday": "Holiday", "mean_units": "Mean units per record"},
                         color_discrete_sequence=[COLORS[2], COLORS[0]]), 310)
            holiday_labels = holidays.holiday.astype(str).str.lower()
            if set(holiday_labels) == {"false", "true"}:
                ordinary = holidays.loc[holiday_labels.eq("false")].iloc[0]
                holiday = holidays.loc[holiday_labels.eq("true")].iloc[0]
                st.caption(f"Holiday-labeled records average {holiday.mean_units - ordinary.mean_units:+.1f} units per record versus ordinary records. This observed difference is not a causal holiday effect.")
        relation = approximate_price_relationship(data)
        if pd.notna(relation["elasticity"]):
            st.info(f"Approximate log-price/log-demand association: {relation['elasticity']:.2f}; log-scale correlation {relation['correlation']:.2f}. {relation['note']}.")
        else:
            st.info(str(relation["note"]))
        price_points = data.groupby(["date", "product_id"], as_index=False).agg(price=("price", "mean"), units=("units", "sum"))
        price_points = price_points[price_points.price.gt(0) & price_points.units.gt(0)]
        if not price_points.empty:
            chart(px.scatter(price_points.sample(min(len(price_points), 800), random_state=42), x="price", y="units",
                             title="Observed price and demand · sampled product-days",
                             labels={"price": f"Price ({currency})", "units": "Units sold"}, color_discrete_sequence=[COLORS[0]]))
        signals, observations = demand_signals(data)
        st.subheader("Demand diagnostics")
        a, b, c, d = st.columns(4)
        a.metric("28-day trend", f"{signals['trend_28d_pct']:+.1f}%" if signals["trend_28d_pct"] is not None else "Unavailable")
        b.metric("Weekly pattern", f"{signals['weekly_strength']:.2f}" if signals["weekly_strength"] is not None else "Unavailable")
        c.metric("Demand volatility", f"{signals['volatility_cv']:.2f}" if signals["volatility_cv"] is not None else "Unavailable")
        d.metric("Unusual days", signals["anomalies"])
        a, b = st.columns(2)
        a.metric("Monthly pattern", f"{signals['monthly_strength']:.2f}" if signals["monthly_strength"] is not None else "Insufficient history")
        b.metric("Annual month-of-year pattern", f"{signals['yearly_strength']:.2f}" if signals["yearly_strength"] is not None else "Insufficient history")
        st.caption("Trend uses a robust 28-day slope. Seasonality and volatility are descriptive. Anomaly flags compare each day with the preceding rolling median and MAD; they do not diagnose the cause.")
        anomalous = observations[observations.anomaly]
        if not anomalous.empty:
            st.dataframe(anomalous[["date", "units", "expected_units", "anomaly_score"]].tail(20).round(1), hide_index=True, width="stretch")


def forecast_lab(data: pd.DataFrame) -> None:
    if st.session_state.get("mode", "m5") == "m5":
        st.info(f"Historical research forecast: M5 observations end {data.date.max():%d %b %Y}. Predicted dates are an archival evaluation, not current operational demand.")
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
            if store != "All stores":
                rates = dict(st.session_state.get("forecast_error_rates", {}))
                rates[(product_id, store)] = max(0.0, float(result.comparison.iloc[0].WAPE) / 100)
                st.session_state.forecast_error_rates = rates
            st.session_state.forecast_key = (product_id, store, horizon, include_ml, include_statistical,
                                             dataset_metadata(data, st.session_state.get("source", "included demo"))["dataset_id"])
        except ValueError as exc:
            st.error(str(exc))
    key = (product_id, store, horizon, include_ml, include_statistical,
           dataset_metadata(data, st.session_state.get("source", "included demo"))["dataset_id"])
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
    fig.add_trace(go.Scatter(x=future.date, y=future.lower, mode="lines", fill="tonexty", fillcolor="rgba(73,213,219,.18)", line=dict(width=0), name="Empirical error band"))
    fig.add_trace(go.Scatter(x=future.date, y=future.forecast, name="Forecast", line=dict(color="#49d5db", width=3)))
    fig.update_layout(title="Observed demand and forecast", yaxis_title="Units/day")
    chart(fig, 430)
    st.caption(f"{result.interval_label}. The errors come from held-out folds and the band is an empirical sensitivity estimate, not guaranteed future coverage. Horizons beyond the backtest window require extra caution.")
    st.subheader("Model comparison · mean across expanding-window folds")
    st.dataframe(result.comparison.round(2), hide_index=True, width="stretch")
    chart(px.bar(result.comparison, x="model", y="WAPE", title="Held-out WAPE by model",
                 labels={"model": "Model", "WAPE": "WAPE (%)"}, color_discrete_sequence=[COLORS[0]]), 320)
    with st.expander("Backtest folds and residuals"):
        st.caption("Each residual is actual minus predicted on a held-out date. Fit-and-predict time includes recursive generation; it is not a hardware-independent benchmark.")
        st.dataframe(result.folds.round(2), hide_index=True, width="stretch")
        residuals = result.residuals[result.residuals.model.eq(result.winner)]
        a, b = st.columns(2)
        with a:
            chart(px.scatter(residuals, x="date", y="residual", color="fold", title="Selected model · residuals over time",
                             labels={"date": "Held-out date", "residual": "Actual − predicted units"}), 330)
        with b:
            chart(px.histogram(residuals, x="residual", nbins=16, title="Selected model · residual distribution",
                               labels={"residual": "Actual − predicted units"}, color_discrete_sequence=[COLORS[1]]), 330)
    with st.expander("Why this model?", expanded=False):
        st.write(f"{result.winner} had the lowest mean held-out WAPE (MAE breaks ties) across expanding-window folds. This selects a model by measured historical errors, not by a claim that it will always win in future periods.")
        if result.winner in {"Random forest", "Gradient boosting"}:
            importance, local = cached_explanations(series, result.winner)
            importance = importance.head(8)
            st.caption("Permutation importance on recent training observations. It shows predictive association, not causal influence.")
            chart(px.bar(importance, x="importance", y="feature", orientation="h", title="Top historical features", color_discrete_sequence=[COLORS[0]]), 330)
            local = local.head(8)
            st.caption("Signed one-feature-at-a-time sensitivity for the first future day, compared with training medians. Correlated effects do not add up and are not causal attributions.")
            chart(px.bar(local, x="signed_change", y="feature", orientation="h", color="direction",
                         title="What raises or lowers the next-day model estimate",
                         labels={"signed_change": "Change in predicted units"},
                         color_discrete_map={"raises": COLORS[0], "lowers": COLORS[3], "neutral": COLORS[4]}), 330)
        else:
            explanations = {"Naive": "Repeats the latest observed day.", "Seasonal naive": "Repeats the last seven-day pattern.",
                            "Moving average": "Uses the mean of the latest 28 days.", "Exponential smoothing": "Weights recent observations more strongly.",
                            "ARIMA": "Uses autoregressive and moving-average structure.", "SARIMA": "Adds a seven-day seasonal autoregressive term."}
            st.info(explanations.get(result.winner, "The model extrapolates past demand patterns."))
    download_csv("Download forecast", result.future, "forecast.csv")
    registry = Path(os.getenv("MODEL_PATH", "artifacts")) / "registry"
    if st.button("Save model run to registry"):
        version = str(dataset_metadata(data, st.session_state.get("source", "included demo"))["checksum"])
        target = register_artifact(result, registry, version)
        st.success(f"Saved versioned model, metrics, residuals and dataset checksum to {target}.")
    saved = list_artifacts(registry)
    if not saved.empty:
        st.subheader("Model registry")
        st.dataframe(saved.drop(columns=["features", "artifact"]).round(2), hide_index=True, width="stretch")
        choices = saved.artifact.tolist()
        selected_run = st.selectbox("Registered run", choices)
        if st.button("Load selected model run"):
            try:
                artifact = load_artifact(registry / selected_run)
                st.info(f"Saved run: {artifact['winner']} · {artifact['trained_at']} · dataset {artifact['dataset_version'][:12]}")
                st.dataframe(artifact["future"], hide_index=True, width="stretch")
            except (OSError, ValueError, KeyError) as exc:
                st.error(f"Could not load this registered run: {exc}")


def inventory_page(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    if plan.empty:
        st.info("No inventory records match your filters.")
        return
    a, b, c, d, e = st.columns(5)
    a.metric("Critical", int(plan.risk.eq("Critical").sum()))
    b.metric("High risk", int(plan.risk.eq("High").sum()))
    c.metric("Suggested units", f"{plan.recommended_order.sum():,}")
    policy = current_risk_settings()
    d.metric("Excess cover", int(plan.days_cover.gt(policy.excess_cover_days).sum()))
    e.metric(f"No sales in {policy.dead_stock_days}+ days", int(plan.dead_stock.sum()))
    planner, segments, simulator, allocation = st.tabs(["Replenishment planner", "ABC × XYZ", "Stockout simulator", "Limited allocation"])
    with planner:
        st.caption("Safety stock = z × daily demand standard deviation × √lead time. Reorder point = mean lead-time demand + safety stock. EOQ assumes fixed order and annual holding costs.")
        shown = plan[["product", "store", "stock", "daily_mean", "days_cover", "days_since_sale", "lead_time", "safety_stock", "reorder_point", "eoq", "recommended_order", "forecast_error_rate", "risk", "reason"]].copy()
        shown.columns = ["Product", "Store", "Current stock", "Daily demand", "Days of cover", "Days since sale", "Lead time", "Safety stock", "Reorder point", "EOQ", "Order units", "Forecast WAPE rate", "Risk", "Reason"]
        st.dataframe(shown.round(1), hide_index=True, width="stretch")
        download_csv("Download recommendations", plan, "replenishment.csv")
    with segments:
        segments = abc_xyz(product_summary(data), st.session_state.get("abc_a", 0.80),
                           st.session_state.get("abc_b", 0.95), st.session_state.get("xyz_x", 0.50),
                           st.session_state.get("xyz_y", 1.00))
        st.dataframe(segments[["product", "revenue", "inventory_value", "demand_cv", "abc", "xyz", "segment", "strategy", "status"]].round(2), hide_index=True, width="stretch")
        st.caption("A/B/C uses cumulative product revenue; X/Y/Z uses the coefficient of variation. Strategy labels follow the displayed segment rules.")
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
    insights = build_insights(data, plan, current_risk_settings())
    for item in insights:
        st.markdown(f'<div class="insight"><small>{html.escape(item["level"].upper())} · {html.escape(item["basis"])}</small><br><b>{html.escape(item["title"])}</b><p>{html.escape(item["detail"])}</p></div>', unsafe_allow_html=True)
    download_csv("Download alerts", pd.DataFrame(insights), "insights.csv")


def reports(data: pd.DataFrame, plan: pd.DataFrame) -> None:
    summary = pd.DataFrame([kpis(data)])
    insights = pd.DataFrame(build_insights(data, plan, current_risk_settings()))
    a, b, c = st.columns(3)
    with a:
        download_csv("Sales dataset · CSV", data, "sales.csv")
    with b:
        download_csv("KPI summary · CSV", summary, "kpis.csv")
    with c:
        if not plan.empty:
            download_csv("Recommendations · CSV", plan, "inventory_recommendations.csv")
    if not insights.empty:
        download_csv("Insights & alerts · CSV", insights, "alerts.csv")
    if "forecast_result" in st.session_state:
        download_csv("Latest forecast · CSV", st.session_state.forecast_result.future, "forecast.csv")
        download_csv("Model metrics · CSV", st.session_state.forecast_result.comparison, "model_metrics.csv")
    st.subheader("Current dataset profile")
    report = assess_quality(data)
    st.json({"source": st.session_state.get("source", "M5 observed sample"), "rows": report.rows, "columns": report.columns,
             "date_start": str(data.date.min().date()), "date_end": str(data.date.max().date()), "health_score": report.score,
             "products": int(data.product_id.nunique()), "stores": int(data.store_id.nunique()),
             "version": dataset_metadata(data, st.session_state.get("source", "M5 observed sample"),
                                         st.session_state.get("dataset_created_at"))})


def settings_page() -> None:
    st.subheader("Inventory policy")
    st.caption("Changing these values recomputes the plan on the next app run. They are session settings, not fitted business parameters.")
    st.slider("Target service level", 0.80, 0.99, 0.95, 0.01, key="service_level")
    a, b = st.columns(2)
    a.slider("A-class revenue cutoff", 0.50, 0.90, 0.80, 0.01, key="abc_a")
    b.slider("B-class revenue cutoff", 0.91, 0.99, 0.95, 0.01, key="abc_b")
    a, b = st.columns(2)
    a.slider("X-class variability cutoff", 0.20, 0.90, 0.50, 0.05, key="xyz_x")
    b.slider("Y-class variability cutoff", 0.95, 2.00, 1.00, 0.05, key="xyz_y")
    st.subheader("Risk rules")
    a, b = st.columns(2)
    a.number_input("No-sales warning days", 14, 90, 30, key="dead_stock_days")
    b.number_input("Excess-cover warning days", 30, 180, 60, key="excess_cover_days")
    a, b, c = st.columns(3)
    a.slider("Volatility risk points", 0, 25, 8, key="volatility_points")
    b.slider("Historical stockout points", 0, 25, 10, key="stockout_points")
    c.slider("Forecast-error points", 0, 25, 10, key="forecast_error_points")
    st.info("Safety stock uses observed demand variability and a normal approximation. ABC is cumulative revenue; XYZ is demand coefficient of variation. Validate these choices with a retailer before operational use.")


def main() -> None:
    if "dataset_created_at" not in st.session_state:
        st.session_state.dataset_created_at = datetime.now(timezone.utc).isoformat()
    all_data = base_data()
    required_inventory = ("stock", "unit_cost", "lead_time", "supplier")
    inventory_ready = all(col in all_data and all_data[col].notna().all() for col in required_inventory)
    pages_available = ["Overview", "Data studio", "Analytics", "Forecast lab", "Inventory", "Insights", "Reports"]
    if inventory_ready:
        pages_available += ["Scenarios", "Settings"]
    with st.sidebar:
        st.markdown('<div class="brand">◈ RetailMind <span>AI</span></div><div class="brand-sub">RETAIL INTELLIGENCE PLATFORM</div>', unsafe_allow_html=True)
        page = st.radio("Workspace", pages_available)
        st.divider()
        start_label = f"{all_data.date.min():%d %b %Y}" if all_data.date.notna().any() else "Dates unavailable"
        end_label = f"{all_data.date.max():%d %b %Y}" if all_data.date.notna().any() else "Dates unavailable"
        st.markdown(f'<div class="sidebar-source"><span>DATA SOURCE</span><strong>{html.escape(st.session_state.get("source", "M5 observed sample"))}</strong><small>{start_label} — {end_label}</small><small>{len(all_data):,} observed rows</small></div>', unsafe_allow_html=True)
        if st.session_state.get("mode", "m5") == "m5" and all_data.date.notna().any():
            st.caption(f"Historical research data · latest observation {all_data.date.max():%Y}")
        elif st.session_state.get("mode", "m5") == "m5":
            st.caption("Historical research data · valid observation dates unavailable")
        else:
            st.caption("Uploaded observed retail data")
    titles = {"Overview": ("Retail intelligence", "An evidence-led view of observed sales and demand."),
              "Data studio": ("Data studio", "Trace each input and inspect data quality."),
              "Analytics": ("Sales analytics", "Explore observed demand by time, product, store and region."),
              "Forecast lab": ("Forecast lab", "Compare models on held-out history and inspect their errors."),
              "Inventory": ("Inventory intelligence", "Inventory measures require observed stock and supply records."),
              "Scenarios": ("What-if scenarios", "Change operating assumptions and see the simulated inventory and margin outcome."),
              "Insights": ("Insights & alerts", "Signals derived from observed sales and demand."),
              "Reports": ("Reports", "Export the observed data and model evidence."),
              "Settings": ("Settings", "Make inventory classification and service assumptions explicit.")}
    if page != "Overview":
        heading(*titles[page])
    if page == "Data studio":
        st.caption("Quality review covers the full dataset, including records with invalid dates.")
        with st.empty().container():
            data_studio(all_data)
        return
    if page == "Settings":
        settings_page()
        return
    if all_data.empty or not all_data.date.notna().any():
        st.warning("The dataset has no valid dated records. Open Data studio to review, clean, or restore it.")
        return
    if page == "Overview":
        with st.expander("Explore date, store, product and category filters", expanded=False):
            filtered = filters(all_data)
    else:
        filtered = filters(all_data)
    if filtered.empty and page != "Data studio":
        st.warning("No records match the selected filters. Broaden the date or entity selection.")
        return
    benchmark_mode = st.session_state.get("mode", "m5") == "m5"
    if benchmark_mode:
        st.caption(f"HISTORICAL M5 OBSERVATIONS · latest recorded sale {filtered.date.max():%d %b %Y} · {filtered.price.isna().sum():,} selected rows have no observed selling price")
    risk_policy = current_risk_settings()
    plan = (pd.DataFrame(columns=["risk", "recommended_order", "days_cover"]) if not inventory_ready else
            cached_plan(filtered, st.session_state.get("service_level", 0.95), risk_policy,
                        dict(st.session_state.get("forecast_error_rates", {}))))
    if not inventory_ready and page == "Inventory":
        missing = [col for col in required_inventory if col not in filtered or filtered[col].isna().any()]
        st.markdown(f'<div class="empty-state"><span class="eyebrow">DATA AVAILABILITY</span><h3>Inventory planning is unavailable</h3><p>Missing observed inputs: {html.escape(", ".join(missing))}. Risk scores, reorder quantities and profit cannot be verified for this selection.</p></div>', unsafe_allow_html=True)
        st.info("Upload real inventory snapshots with stock, unit_cost, supplier and lead_time in Data studio to enable planning.")
        return
    pages = {"Overview": overview, "Analytics": analytics, "Forecast lab": forecast_lab,
             "Inventory": inventory_page, "Scenarios": scenarios, "Insights": insights_page, "Reports": reports}
    page_slot = st.empty()
    with page_slot.container():
        if page in {"Overview", "Inventory", "Scenarios", "Insights", "Reports"}:
            pages[page](filtered, plan)
        else:
            pages[page](filtered)
    st.markdown('<p class="footer-note">RetailMind AI · Observations, forecasts and simulations are labeled separately. Inventory recommendations require business review.</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()

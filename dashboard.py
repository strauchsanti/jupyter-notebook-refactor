"""Streamlit dashboard for the e-commerce sales analysis.

Run with:  streamlit run dashboard.py

The date range filter in the header applies to every card and chart. Trend
indicators compare the selected range with the period of equal length that
comes right before it. All calculations come from business_metrics.py and
data_loader.py; this file only handles layout and formatting.
"""

import math
from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import business_metrics as bm
import data_loader as dl

DATA_DIR = "ecommerce_data"
DEFAULT_START = "2023-01"
DEFAULT_END = "2023-12"
DELIVERY_BINS = bm.DEFAULT_DELIVERY_BINS
DELIVERY_LABELS = bm.DEFAULT_DELIVERY_LABELS

COLOR_CURRENT = "#1f4e79"
COLOR_PREVIOUS = "#8c9bab"
COLOR_UP = "#1a7f37"
COLOR_DOWN = "#cf222e"
COLOR_FLAT = "#6b7785"
BLUE_SCALE = [[0.0, "#c6dbef"], [0.5, "#4292c6"], [1.0, "#08306b"]]
CHART_HEIGHT = 380

st.set_page_config(page_title="E-commerce Sales Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1400px;}
    .dash-title {font-size: 1.9rem; font-weight: 700; color: #1f2d3d; margin: 0; line-height: 1.2;}
    .dash-subtitle {color: #5b6b7f; font-size: 0.9rem; margin-top: 0.25rem;}
    .card {background: #ffffff; border: 1px solid #e3e8ef; border-radius: 10px;
           padding: 16px 20px; box-sizing: border-box; overflow: hidden;}
    .kpi-card {height: 150px;}
    .info-card {height: 150px;}
    .card-label {font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em;
                 color: #5b6b7f; font-weight: 600;}
    .card-value {font-size: 2.1rem; font-weight: 700; color: #1f2d3d; line-height: 1.2; margin-top: 6px;}
    .card-unit {font-size: 1rem; font-weight: 500; color: #5b6b7f; margin-left: 4px;}
    .card-trend {font-size: 0.9rem; font-weight: 600; margin-top: 6px;}
    .card-note {font-weight: 400; color: #5b6b7f; margin-left: 6px;}
    .card-subtitle {font-size: 0.85rem; color: #5b6b7f; margin-top: 4px;}
    .trend-up {color: #1a7f37;}
    .trend-down {color: #cf222e;}
    .trend-flat {color: #6b7785;}
    .score-row {display: flex; align-items: baseline; gap: 14px;}
    .stars {font-size: 1.7rem; letter-spacing: 2px; line-height: 1; white-space: nowrap;
            background: linear-gradient(90deg, #f5a623 var(--fill), #d5dbe3 var(--fill));
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; color: transparent;}
    div[data-testid="stVerticalBlockBorderWrapper"] {background: #ffffff;}
    </style>
    """,
    unsafe_allow_html=True,
)


# Formatting helpers ----------------------------------------------------------

def format_money(value: float) -> str:
    """Format a currency amount compactly, for example $300K or $2M."""
    if value is None or pd.isna(value):
        return "n/a"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1e6:
        return f"{sign}${magnitude / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    if magnitude >= 1e3:
        return f"{sign}${magnitude / 1e3:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{sign}${magnitude:,.0f}"


def nice_ticks(max_value: float, target_count: int = 5) -> List[float]:
    """Round tick positions from zero up to (and just beyond) max_value."""
    if max_value is None or pd.isna(max_value) or max_value <= 0:
        return [0.0]
    raw_step = max_value / target_count
    magnitude = 10 ** math.floor(math.log10(raw_step))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw_step)
    return list(np.arange(0, max_value + step, step))


def money_axis(max_value: float) -> dict:
    """Plotly axis settings that label ticks as $300K or $2M."""
    ticks = nice_ticks(max_value)
    return {"tickvals": ticks, "ticktext": [format_money(t) for t in ticks]}


def pretty_category(name: str) -> str:
    """Turn product_category_name values like home_garden into Home Garden."""
    return str(name).replace("_", " ").title()


def trend_html(current: float, previous: float, lower_is_better: bool = False) -> str:
    """Trend line with arrow, percent change to two decimals and colour.

    Positive changes are green and negative changes red, unless lower_is_better
    is set (used for delivery time, where a decrease is the favourable move).
    """
    change = bm.growth_rate(current, previous)
    if pd.isna(change):
        return '<div class="card-trend trend-flat">n/a<span class="card-note">no comparison data</span></div>'
    if round(100 * change, 2) == 0:
        css, arrow = "trend-flat", "&ndash;"
    else:
        favourable = (change < 0) if lower_is_better else (change > 0)
        css = "trend-up" if favourable else "trend-down"
        arrow = "&#9650;" if change > 0 else "&#9660;"
    return (f'<div class="card-trend {css}">{arrow} {abs(100 * change):.2f}%'
            f'<span class="card-note">vs previous period</span></div>')


def kpi_card(label: str, value: str, trend: str = "", note: str = "") -> str:
    """HTML for one KPI card. `note` replaces the trend line when there is none."""
    footer = trend or (f'<div class="card-trend trend-flat">{note}</div>' if note else "")
    return (f'<div class="card kpi-card"><div class="card-label">{label}</div>'
            f'<div class="card-value">{value}</div>{footer}</div>')


# Data ------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading data")
def load_sales() -> pd.DataFrame:
    """Load and join the whole dataset once; filtering happens per interaction."""
    return dl.build_sales_data(dl.load_raw_tables(DATA_DIR))


sales_all = load_sales()
first_month, last_month = dl.available_period_range(sales_all)
month_range = pd.period_range(first_month, last_month, freq="M")
month_labels = [m.strftime("%b %Y") for m in month_range]
label_to_period = dict(zip(month_labels, month_range))


def default_label(month_text: str, fallback: str) -> str:
    """Label of a configured default month, or a fallback if outside the data."""
    label = pd.Period(month_text, freq="M").strftime("%b %Y")
    return label if label in label_to_period else fallback


# Header ----------------------------------------------------------------------

title_col, filter_col = st.columns([3, 2], vertical_alignment="center")
with filter_col:
    start_label, end_label = st.select_slider(
        "Date range (months)",
        options=month_labels,
        value=(default_label(DEFAULT_START, month_labels[0]),
               default_label(DEFAULT_END, month_labels[-1])),
    )

current_start, current_end = label_to_period[start_label], label_to_period[end_label]
previous_start, previous_end = dl.get_comparison_period(
    current_start.strftime("%Y-%m"), current_end.strftime("%Y-%m")
)
period_label = f"{start_label} to {end_label}"
previous_label = f"{previous_start.strftime('%b %Y')} to {previous_end.strftime('%b %Y')}"
n_months = (current_end - current_start).n + 1

with title_col:
    st.markdown(
        f'<div class="dash-title">E-commerce Sales Dashboard</div>'
        f'<div class="dash-subtitle">{period_label}. Trends compare with {previous_label}.</div>',
        unsafe_allow_html=True,
    )

# Filtered data ---------------------------------------------------------------

sales = dl.filter_by_period(sales_all, current_start, current_end)
sales_previous = dl.filter_by_period(sales_all, previous_start, previous_end)
delivered = dl.delivered_only(sales)
delivered_previous = dl.delivered_only(sales_previous)

if previous_start < first_month:
    # A comparison period only partly covered by the data would give misleading trends.
    st.caption(f"Trends are not shown because the comparison period ({previous_label}) "
               f"starts before the first month in the data ({first_month.strftime('%b %Y')}).")
    sales_previous = sales_previous.iloc[0:0]
    delivered_previous = delivered_previous.iloc[0:0]
if delivered.empty:
    st.warning("There are no delivered orders in the selected date range.")
    st.stop()

revenue = bm.total_revenue(delivered)
revenue_previous = bm.total_revenue(delivered_previous)
aov = bm.average_order_value(delivered)
aov_previous = bm.average_order_value(delivered_previous)
orders_count = bm.total_orders(delivered)
orders_previous = bm.total_orders(delivered_previous)
avg_growth = bm.average_month_over_month_growth(delivered)
delivery_days = bm.average_delivery_days(delivered)
delivery_days_previous = bm.average_delivery_days(delivered_previous)
review_score = bm.average_review_score(delivered)

# KPI row ---------------------------------------------------------------------

st.write("")
k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi_card("Total Revenue", format_money(revenue),
                     trend_html(revenue, revenue_previous)), unsafe_allow_html=True)
if pd.isna(avg_growth):
    growth_value = "n/a"
    growth_note = "Needs at least two months"
else:
    growth_value = f"{100 * avg_growth:+.2f}%"
    growth_note = "Average month over month"
k2.markdown(kpi_card("Monthly Growth", growth_value, note=growth_note), unsafe_allow_html=True)
k3.markdown(kpi_card("Average Order Value", f"${aov:,.2f}",
                     trend_html(aov, aov_previous)), unsafe_allow_html=True)
k4.markdown(kpi_card("Total Orders", f"{orders_count:,}",
                     trend_html(orders_count, orders_previous)), unsafe_allow_html=True)


# Charts ----------------------------------------------------------------------

def style_figure(fig: go.Figure, title: str) -> go.Figure:
    """Apply the shared layout (title with date range, height, margins, fonts)."""
    fig.update_layout(
        title={"text": f"{title}<br><sup>{period_label}</sup>", "x": 0.0, "xanchor": "left"},
        height=CHART_HEIGHT,
        margin={"l": 10, "r": 10, "t": 70, "b": 10},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"color": "#1f2d3d"},
    )
    return fig


def revenue_trend_figure() -> go.Figure:
    """Monthly revenue: solid line for the selected range, dashed for the previous range.

    The previous range is drawn on the same x positions as the selected one
    (first month over first month); hover shows its actual month.
    """
    current_months = pd.period_range(current_start, current_end, freq="M")
    current = bm.monthly_revenue(delivered).reindex(current_months, fill_value=0.0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=current_months.to_timestamp(), y=current.values, mode="lines+markers",
        name=period_label, line={"color": COLOR_CURRENT, "width": 3},
        customdata=[format_money(v) for v in current.values],
        hovertemplate="%{x|%b %Y}<br>Revenue: %{customdata}<extra></extra>",
    ))
    values = list(current.values)
    if not delivered_previous.empty:
        previous_months = pd.period_range(previous_start, previous_end, freq="M")
        previous = bm.monthly_revenue(delivered_previous).reindex(previous_months, fill_value=0.0)
        fig.add_trace(go.Scatter(
            x=current_months.to_timestamp(), y=previous.values, mode="lines+markers",
            name=previous_label, line={"color": COLOR_PREVIOUS, "width": 3, "dash": "dash"},
            customdata=np.column_stack([
                [m.strftime("%b %Y") for m in previous_months],
                [format_money(v) for v in previous.values],
            ]),
            hovertemplate="%{customdata[0]}<br>Revenue: %{customdata[1]}<extra></extra>",
        ))
        values += list(previous.values)
    fig.update_xaxes(showgrid=True, gridcolor="#e8ecf1", tickformat="%b %Y", title_text="Month of purchase")
    fig.update_yaxes(showgrid=True, gridcolor="#e8ecf1", rangemode="tozero",
                     title_text="Revenue (USD)", **money_axis(max(values)))
    fig.update_layout(legend={"orientation": "h", "y": -0.25, "x": 0})
    return style_figure(fig, "Revenue Trend")


def category_figure() -> go.Figure:
    """Top 10 categories by revenue, largest first, in a light-to-dark blue gradient."""
    top = bm.revenue_by_category(delivered).head(10)
    fig = go.Figure(go.Bar(
        x=top.values, y=[pretty_category(c) for c in top.index], orientation="h",
        marker={"color": top.values, "colorscale": BLUE_SCALE, "cmin": 0, "cmax": float(top.max())},
        text=[format_money(v) for v in top.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Revenue: %{text}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", title_text="Product category")
    fig.update_xaxes(showgrid=True, gridcolor="#e8ecf1", title_text="Revenue (USD)",
                     range=[0, float(top.max()) * 1.18], **money_axis(float(top.max())))
    return style_figure(fig, "Top 10 Categories by Revenue")


def state_map_figure() -> go.Figure:
    """US choropleth of revenue by customer state, in a blue gradient."""
    states = bm.revenue_by_state(delivered)
    top = float(states["price"].max())
    ticks = money_axis(top)
    fig = go.Figure(go.Choropleth(
        locations=states["customer_state"], z=states["price"], locationmode="USA-states",
        colorscale=BLUE_SCALE, zmin=0, zmax=top,
        customdata=[format_money(v) for v in states["price"]],
        hovertemplate="%{location}<br>Revenue: %{customdata}<extra></extra>",
        colorbar={"title": {"text": "Revenue (USD)"}, "thickness": 12, **ticks},
        marker={"line": {"color": "white", "width": 0.6}},
    ))
    fig.update_geos(scope="usa", bgcolor="white", showlakes=False)
    return style_figure(fig, "Revenue by State")


def satisfaction_figure() -> go.Figure:
    """Average review score for each delivery time bucket."""
    table = bm.review_score_by_delivery_bucket(delivered, DELIVERY_BINS, DELIVERY_LABELS)
    scores = table["avg_review_score"]
    fig = go.Figure(go.Bar(
        x=table["delivery_bucket"].astype(str), y=scores, marker={"color": COLOR_CURRENT},
        text=[f"{s:.2f}" if pd.notna(s) else "n/a" for s in scores], textposition="outside",
        customdata=table["orders"],
        hovertemplate="%{x}<br>Average score: %{text}<br>Reviewed orders: %{customdata:,}<extra></extra>",
    ))
    fig.update_xaxes(title_text="Delivery time (days from purchase to delivery)")
    fig.update_yaxes(title_text="Average review score (1 to 5)", range=[0, 5.5],
                     tickvals=[0, 1, 2, 3, 4, 5], showgrid=True, gridcolor="#e8ecf1")
    return style_figure(fig, "Customer Satisfaction by Delivery Time")


st.write("")
chart_row_1 = st.columns(2)
chart_row_2 = st.columns(2)
for slot, build in [
    (chart_row_1[0], revenue_trend_figure),
    (chart_row_1[1], category_figure),
    (chart_row_2[0], state_map_figure),
    (chart_row_2[1], satisfaction_figure),
]:
    with slot, st.container(border=True):
        st.plotly_chart(build(), use_container_width=True)

# Bottom row ------------------------------------------------------------------

st.write("")
b1, b2 = st.columns(2)
delivery_value = "n/a" if pd.isna(delivery_days) else f"{delivery_days:.2f}"
b1.markdown(
    f'<div class="card info-card"><div class="card-label">Average Delivery Time</div>'
    f'<div class="card-value">{delivery_value}<span class="card-unit">days</span></div>'
    f'{trend_html(delivery_days, delivery_days_previous, lower_is_better=True)}</div>',
    unsafe_allow_html=True,
)
if pd.isna(review_score):
    score_html = '<div class="card-value">n/a</div>'
else:
    score_html = (f'<div class="score-row"><div class="card-value">{review_score:.2f}</div>'
                  f'<div class="stars" style="--fill: {100 * review_score / 5:.1f}%">&#9733;&#9733;&#9733;&#9733;&#9733;</div></div>')
b2.markdown(
    f'<div class="card info-card"><div class="card-label">Review Score</div>{score_html}'
    f'<div class="card-subtitle">Average Review Score</div></div>',
    unsafe_allow_html=True,
)

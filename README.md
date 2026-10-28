# E-commerce Sales Analysis

Exploratory analysis of an e-commerce dataset (orders, items, products, customers and reviews).
`EDA.ipynb` is the original notebook. `EDA_Refactored.ipynb` is the same analysis with a clearer
structure, reusable functions and a configurable date range.

## Project layout

| File | Purpose |
|---|---|
| `EDA.ipynb` | Original exploratory notebook |
| `EDA_Refactored.ipynb` | Refactored notebook: documentation, data dictionary, charts and summary |
| `dashboard.py` | Streamlit dashboard built on the two modules below |
| `.streamlit/config.toml` | Dashboard theme (light) |
| `data_loader.py` | Loads the CSV files, joins them, derives columns, filters by month range |
| `business_metrics.py` | Metric calculations only (revenue, orders, products, states, reviews, delivery, status) |
| `requirements.txt` | Python dependencies |
| `ecommerce_data/` | Source CSV files |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook EDA_Refactored.ipynb
```

## Streamlit dashboard

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard.py
```

The dashboard opens in your browser. Layout:

- **Header:** title on the left, date range filter on the right (month granularity). The filter applies to every card and chart.
- **KPI row:** Total Revenue, Monthly Growth (average month-over-month), Average Order Value and Total Orders.
- **Charts (2x2):** revenue trend (solid = selected range, dashed = previous period), top 10 categories, revenue by state map, and average review score by delivery time.
- **Bottom row:** average delivery time and average review score.

Notes on how it behaves:

- Trend indicators compare the selected range with the period of equal length right before it, shown to two decimals. Green is a favourable change and red an unfavourable one. For delivery time, a decrease is treated as favourable (green).
- If the comparison period starts before the first month in the data, trends show "n/a" instead of a misleading figure.
- Monthly Growth needs at least two months in the range.
- The data contains only a sliver of December 2021 and January 2024, so ranges ending or starting there have very small first or last months.
- Revenue, orders and averages use delivered orders only. Delivery time and review score use delivered orders that have a review.
- Run the dashboard from the project folder so it finds `ecommerce_data/`.

## Using the refactored analysis

Open `EDA_Refactored.ipynb` and edit the configuration cell in section 3, then run all cells.

```python
START_MONTH = "2023-01"          # first month of the analysis period
END_MONTH = "2023-12"            # last month (inclusive)
COMPARISON_START_MONTH = None    # optional; None = equal-length period right before START_MONTH
COMPARISON_END_MONTH = None
DELIVERY_BINS = (3, 7)           # upper edge in days of every delivery group except the last
DELIVERY_LABELS = ("1-3 days", "4-7 days", "8+ days")
```

Examples:

- Full year 2023 against 2022 (default): `"2023-01"` to `"2023-12"`.
- Second quarter 2023 against the first quarter: `"2023-04"` to `"2023-06"`.
- A custom comparison, such as Q2 2023 against Q2 2022: also set `COMPARISON_START_MONTH = "2022-04"` and `COMPARISON_END_MONTH = "2022-06"`.

Months are assigned by order purchase date. Revenue is the sum of item prices of delivered orders,
excluding freight. Delivery time and review metrics only use delivered orders that have a review score.
Charts and the summary text pick up the selected range automatically.

## Using the modules outside the notebook

```python
import data_loader as dl
import business_metrics as bm

data = dl.prepare_analysis_data("2023-04", "2023-06", data_dir="ecommerce_data")
delivered = data["sales_delivered"]

bm.total_revenue(delivered)
bm.revenue_by_category(delivered)
bm.kpi_summary(delivered, data["sales_delivered_previous"])
```

To apply the code to a new dataset with the same table layout, point `data_dir` at the new folder.
If column names differ, adjust `TABLE_FILES` and `build_sales_data` in `data_loader.py`; the metric
functions only rely on the columns of the item-level table (`order_id`, `price`, `year_month`,
`product_category_name`, `customer_state`, `delivery_days`, `review_score`, `order_status`).

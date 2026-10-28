# E-commerce Sales Analysis

Exploratory analysis of an e-commerce dataset (orders, items, products, customers and reviews).
`EDA.ipynb` is the original notebook. `EDA_Refactored.ipynb` is the same analysis with a clearer
structure, reusable functions and a configurable date range.

## Project layout

| File | Purpose |
|---|---|
| `EDA.ipynb` | Original exploratory notebook |
| `EDA_Refactored.ipynb` | Refactored notebook: documentation, data dictionary, charts and summary |
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

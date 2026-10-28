"""Data loading, cleaning and preparation for the e-commerce analysis.

The functions in this module read the raw CSV files, join them into a single
item-level table and filter that table to a configurable month range. No
business metrics are calculated here; see business_metrics.py for those.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

DEFAULT_DATA_DIR = "ecommerce_data"

TABLE_FILES = {
    "orders": "orders_dataset.csv",
    "order_items": "order_items_dataset.csv",
    "products": "products_dataset.csv",
    "customers": "customers_dataset.csv",
    "reviews": "order_reviews_dataset.csv",
    "payments": "order_payments_dataset.csv",
}

DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}

DELIVERED_STATUS = "delivered"


def load_raw_tables(data_dir: str = DEFAULT_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Load every CSV file of the dataset and parse its date columns.

    Args:
        data_dir: Folder containing the *_dataset.csv files.

    Returns:
        Dictionary mapping a table name (for example "orders") to its DataFrame.

    Raises:
        FileNotFoundError: If one of the expected files is missing.
    """
    data_path = Path(data_dir)
    tables = {}
    for name, file_name in TABLE_FILES.items():
        file_path = data_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"Expected data file not found: {file_path}")
        tables[name] = pd.read_csv(
            file_path, parse_dates=DATE_COLUMNS.get(name, [])
        )
    return tables


def build_sales_data(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join order items with order, product, customer and review information.

    The result has one row per order item. Review scores are attached at order
    level, so every item of an order carries the same score. Orders without a
    review keep a missing score.

    Args:
        tables: Output of load_raw_tables.

    Returns:
        Item-level DataFrame with the extra columns year, month, year_month
        (monthly Period) and delivery_days (whole days between purchase and
        delivery, missing when the order was not delivered).
    """
    orders = tables["orders"][
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_delivered_customer_date",
        ]
    ]
    items = tables["order_items"][
        ["order_id", "order_item_id", "product_id", "price", "freight_value"]
    ]
    products = tables["products"][["product_id", "product_category_name"]]
    customers = tables["customers"][["customer_id", "customer_state"]]
    reviews = (
        tables["reviews"].groupby("order_id", as_index=False)["review_score"].mean()
    )

    sales = (
        items.merge(orders, on="order_id", how="inner")
        .merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
        .merge(reviews, on="order_id", how="left")
    )

    purchase = sales["order_purchase_timestamp"]
    sales["year"] = purchase.dt.year
    sales["month"] = purchase.dt.month
    sales["year_month"] = purchase.dt.to_period("M")
    sales["delivery_days"] = (
        sales["order_delivered_customer_date"] - purchase
    ).dt.days
    return sales


def add_order_year_month(orders: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the orders table with a year_month Period column."""
    orders = orders.copy()
    orders["year_month"] = orders["order_purchase_timestamp"].dt.to_period("M")
    return orders


def parse_period(start: str, end: str) -> Tuple[pd.Period, pd.Period]:
    """Convert two "YYYY-MM" strings into monthly Periods.

    Raises:
        ValueError: If the end month is before the start month.
    """
    start_period = pd.Period(start, freq="M")
    end_period = pd.Period(end, freq="M")
    if end_period < start_period:
        raise ValueError(f"End month {end} is before start month {start}.")
    return start_period, end_period


def get_comparison_period(
    start: str, end: str
) -> Tuple[pd.Period, pd.Period]:
    """Return the period of equal length that ends right before `start`.

    For example, 2023-01 to 2023-12 gives 2022-01 to 2022-12, and 2023-04 to
    2023-06 gives 2023-01 to 2023-03.
    """
    start_period, end_period = parse_period(start, end)
    length = (end_period - start_period).n + 1
    return start_period - length, start_period - 1


def filter_by_period(
    data: pd.DataFrame,
    start: pd.Period,
    end: pd.Period,
    period_column: str = "year_month",
) -> pd.DataFrame:
    """Keep rows whose monthly Period lies between start and end, inclusive."""
    mask = (data[period_column] >= start) & (data[period_column] <= end)
    return data.loc[mask].copy()


def delivered_only(data: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows belonging to delivered orders."""
    return data.loc[data["order_status"] == DELIVERED_STATUS].copy()


def available_period_range(data: pd.DataFrame) -> Tuple[pd.Period, pd.Period]:
    """Return the first and last month present in the data."""
    return data["year_month"].min(), data["year_month"].max()


def prepare_analysis_data(
    start: str,
    end: str,
    data_dir: str = DEFAULT_DATA_DIR,
    comparison_start: Optional[str] = None,
    comparison_end: Optional[str] = None,
) -> Dict[str, object]:
    """Load the data and split it into the analysis and comparison periods.

    Args:
        start: First month of the analysis period, "YYYY-MM".
        end: Last month of the analysis period, "YYYY-MM".
        data_dir: Folder containing the CSV files.
        comparison_start: First month of the comparison period. If omitted, the
            period of equal length right before the analysis period is used.
        comparison_end: Last month of the comparison period. Must be given
            together with comparison_start.

    Returns:
        Dictionary with the keys:
            periods: dict with "current" and "previous" (start, end) Periods.
            sales: item-level table, analysis period, all order statuses.
            sales_previous: same for the comparison period.
            sales_delivered: delivered items of the analysis period.
            sales_delivered_previous: delivered items of the comparison period.
            orders: orders of the analysis period, all statuses.
            orders_previous: orders of the comparison period.
    """
    if (comparison_start is None) != (comparison_end is None):
        raise ValueError("Provide both comparison_start and comparison_end, or neither.")

    current = parse_period(start, end)
    if comparison_start is None:
        previous = get_comparison_period(start, end)
    else:
        previous = parse_period(comparison_start, comparison_end)

    tables = load_raw_tables(data_dir)
    sales_all = build_sales_data(tables)
    orders_all = add_order_year_month(tables["orders"])

    sales = filter_by_period(sales_all, *current)
    sales_previous = filter_by_period(sales_all, *previous)

    return {
        "periods": {"current": current, "previous": previous},
        "sales": sales,
        "sales_previous": sales_previous,
        "sales_delivered": delivered_only(sales),
        "sales_delivered_previous": delivered_only(sales_previous),
        "orders": filter_by_period(orders_all, *current),
        "orders_previous": filter_by_period(orders_all, *previous),
    }

"""Business metric calculations for the e-commerce analysis.

Every function takes an already filtered DataFrame (see data_loader.py), so the
same code works for any month range. Revenue functions expect delivered items
only; the order status function expects the orders table.
"""

from typing import Dict, List, Optional, Sequence

import pandas as pd

DEFAULT_DELIVERY_BINS = (3, 7)
DEFAULT_DELIVERY_LABELS = ("1-3 days", "4-7 days", "8+ days")


def growth_rate(current: float, previous: float) -> float:
    """Relative change from previous to current, as a fraction (0.05 is +5%).

    Returns NaN when the previous value is zero or missing.
    """
    if previous is None or pd.isna(previous) or previous == 0:
        return float("nan")
    return (current - previous) / previous


# Revenue ---------------------------------------------------------------------

def total_revenue(sales_delivered: pd.DataFrame) -> float:
    """Sum of item prices of delivered orders (freight excluded)."""
    return float(sales_delivered["price"].sum())


def total_orders(sales_delivered: pd.DataFrame) -> int:
    """Number of distinct delivered orders."""
    return int(sales_delivered["order_id"].nunique())


def average_order_value(sales_delivered: pd.DataFrame) -> float:
    """Mean order value, where an order's value is the sum of its item prices."""
    if sales_delivered.empty:
        return float("nan")
    return float(sales_delivered.groupby("order_id")["price"].sum().mean())


def monthly_revenue(sales_delivered: pd.DataFrame) -> pd.Series:
    """Revenue per calendar month, indexed by monthly Period."""
    return sales_delivered.groupby("year_month")["price"].sum().sort_index()


def month_over_month_growth(sales_delivered: pd.DataFrame) -> pd.Series:
    """Revenue growth versus the previous month, as fractions.

    Months with no delivered sales inside the range are filled with zero revenue
    so that growth is always measured between consecutive calendar months.
    """
    revenue = monthly_revenue(sales_delivered)
    if revenue.empty:
        return revenue
    full_index = pd.period_range(revenue.index.min(), revenue.index.max(), freq="M")
    return revenue.reindex(full_index, fill_value=0.0).pct_change()


def average_month_over_month_growth(sales_delivered: pd.DataFrame) -> float:
    """Simple mean of the month-over-month growth rates."""
    return float(month_over_month_growth(sales_delivered).mean())


# Products --------------------------------------------------------------------

def revenue_by_category(sales_delivered: pd.DataFrame) -> pd.Series:
    """Revenue per product category, largest first."""
    return (
        sales_delivered.groupby("product_category_name")["price"]
        .sum()
        .sort_values(ascending=False)
    )


# Geography -------------------------------------------------------------------

def revenue_by_state(sales_delivered: pd.DataFrame) -> pd.DataFrame:
    """Revenue per customer state, largest first.

    Returns:
        DataFrame with the columns customer_state and price (revenue).
    """
    return (
        sales_delivered.groupby("customer_state")["price"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )


# Customer experience ---------------------------------------------------------

def order_level_reviews(sales: pd.DataFrame) -> pd.DataFrame:
    """One row per delivered, reviewed order with delivery days and score."""
    delivered = sales[sales["order_status"] == "delivered"]
    return (
        delivered[["order_id", "delivery_days", "review_score"]]
        .dropna(subset=["review_score", "delivery_days"])
        .drop_duplicates(subset="order_id")
    )


def average_delivery_days(sales_delivered: pd.DataFrame) -> float:
    """Mean delivery time in whole days, over delivered orders with a review."""
    return float(order_level_reviews(sales_delivered)["delivery_days"].mean())


def average_review_score(sales_delivered: pd.DataFrame) -> float:
    """Mean review score over delivered orders with a review."""
    return float(order_level_reviews(sales_delivered)["review_score"].mean())


def review_score_distribution(sales_delivered: pd.DataFrame) -> pd.Series:
    """Share of delivered, reviewed orders per review score (sums to 1)."""
    scores = order_level_reviews(sales_delivered)["review_score"]
    return scores.value_counts(normalize=True).sort_index()


def review_score_by_delivery_days(sales_delivered: pd.DataFrame) -> pd.DataFrame:
    """Mean review score and order count for each whole-day delivery time."""
    reviews = order_level_reviews(sales_delivered)
    return (
        reviews.groupby("delivery_days")["review_score"]
        .agg(avg_review_score="mean", orders="count")
        .reset_index()
    )


def review_score_by_delivery_bucket(
    sales_delivered: pd.DataFrame,
    bins: Sequence[float] = DEFAULT_DELIVERY_BINS,
    labels: Sequence[str] = DEFAULT_DELIVERY_LABELS,
) -> pd.DataFrame:
    """Mean review score and order count per delivery time bucket.

    Args:
        sales_delivered: Delivered items.
        bins: Inclusive upper edge in days of every bucket except the last,
            which is open ended. The default (3, 7) reproduces the original
            analysis: up to 3 days, 4 to 7 days and 8+ days.
        labels: One label per bucket, so len(labels) == len(bins) + 1.
    """
    if len(labels) != len(bins) + 1:
        raise ValueError("labels must contain exactly one more item than bins.")
    reviews = order_level_reviews(sales_delivered).copy()
    edges = [float("-inf")] + list(bins) + [float("inf")]
    reviews["delivery_bucket"] = pd.cut(
        reviews["delivery_days"], bins=edges, labels=list(labels), right=True
    )
    return (
        reviews.groupby("delivery_bucket", observed=False)["review_score"]
        .agg(avg_review_score="mean", orders="count")
        .reset_index()
    )


def order_status_distribution(orders: pd.DataFrame) -> pd.Series:
    """Share of orders per status (sums to 1), largest first."""
    return orders["order_status"].value_counts(normalize=True)


# Summary ---------------------------------------------------------------------

def kpi_summary(
    sales_delivered: pd.DataFrame, sales_delivered_previous: pd.DataFrame
) -> pd.DataFrame:
    """Headline KPIs for the analysis period versus the comparison period.

    Returns:
        DataFrame indexed by KPI name with the columns current, previous and
        change_pct (percent change, NaN when the previous value is zero).
    """
    rows = {
        "Total revenue": (total_revenue(sales_delivered), total_revenue(sales_delivered_previous)),
        "Total orders": (total_orders(sales_delivered), total_orders(sales_delivered_previous)),
        "Average order value": (
            average_order_value(sales_delivered),
            average_order_value(sales_delivered_previous),
        ),
        "Average review score": (
            average_review_score(sales_delivered),
            average_review_score(sales_delivered_previous),
        ),
        "Average delivery days": (
            average_delivery_days(sales_delivered),
            average_delivery_days(sales_delivered_previous),
        ),
    }
    summary = pd.DataFrame(rows, index=["current", "previous"]).T
    summary["change_pct"] = [
        100 * growth_rate(cur, prev) for cur, prev in zip(summary["current"], summary["previous"])
    ]
    return summary

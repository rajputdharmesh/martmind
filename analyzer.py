"""
analyzer.py  –  All analytics queries powered by SQL + pandas.
Every function returns a DataFrame ready for Plotly / Streamlit.
"""

import pandas as pd
from .database import get_connection


def _q(sql: str, params=()) -> pd.DataFrame:
    conn = get_connection()
    df   = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# ── Overview ──────────────────────────────────────────────────────────────────

def monthly_spend() -> pd.DataFrame:
    """Total spending per month."""
    return _q("""
        SELECT strftime('%Y-%m', purchase_date) AS month,
               ROUND(SUM(total_amount), 2)      AS total_spend
        FROM   bills
        GROUP  BY month
        ORDER  BY month
    """)


def category_spend(month: str = None) -> pd.DataFrame:
    """Spending broken down by category, optionally filtered to one month."""
    if month:
        return _q("""
            SELECT c.name        AS category,
                   ROUND(SUM(bi.price * bi.quantity - bi.discount), 2) AS spend
            FROM   bill_items bi
            JOIN   bills      b  ON b.id  = bi.bill_id
            JOIN   items      i  ON i.id  = bi.item_id
            JOIN   categories c  ON c.id  = i.category_id
            WHERE  strftime('%Y-%m', b.purchase_date) = ?
            GROUP  BY c.name
            ORDER  BY spend DESC
        """, (month,))
    return _q("""
        SELECT c.name        AS category,
               ROUND(SUM(bi.price * bi.quantity - bi.discount), 2) AS spend
        FROM   bill_items bi
        JOIN   bills      b  ON b.id  = bi.bill_id
        JOIN   items      i  ON i.id  = bi.item_id
        JOIN   categories c  ON c.id  = i.category_id
        GROUP  BY c.name
        ORDER  BY spend DESC
    """)


def top_items(limit: int = 10, month: str = None) -> pd.DataFrame:
    """Most frequently purchased items."""
    if month:
        return _q("""
            SELECT i.name AS item, COUNT(*) AS times_bought,
                   ROUND(SUM(bi.price * bi.quantity), 2) AS total_spent
            FROM   bill_items bi
            JOIN   bills      b ON b.id = bi.bill_id
            JOIN   items      i ON i.id = bi.item_id
            WHERE  strftime('%Y-%m', b.purchase_date) = ?
            GROUP  BY i.name
            ORDER  BY times_bought DESC
            LIMIT  ?
        """, (month, limit))
    return _q("""
        SELECT i.name AS item, COUNT(*) AS times_bought,
               ROUND(SUM(bi.price * bi.quantity), 2) AS total_spent
        FROM   bill_items bi
        JOIN   items      i ON i.id = bi.item_id
        GROUP  BY i.name
        ORDER  BY times_bought DESC
        LIMIT  ?
    """, (limit,))


def summary_stats() -> dict:
    df = _q("""
        SELECT COUNT(DISTINCT b.id)                     AS total_bills,
               ROUND(SUM(b.total_amount), 2)            AS total_spent,
               ROUND(AVG(b.total_amount), 2)            AS avg_bill,
               COUNT(DISTINCT i.id)                     AS unique_items
        FROM   bills      b
        JOIN   bill_items bi ON bi.bill_id = b.id
        JOIN   items      i  ON i.id       = bi.item_id
    """)
    return df.iloc[0].to_dict() if not df.empty else {}


# ── Inflation tracker ─────────────────────────────────────────────────────────

def item_price_over_time(item_name: str) -> pd.DataFrame:
    """Price history of a specific item across all bills."""
    return _q("""
        SELECT strftime('%Y-%m', b.purchase_date) AS month,
               ROUND(AVG(bi.price), 2)            AS avg_price,
               s.name                             AS store
        FROM   bill_items bi
        JOIN   bills      b ON b.id = bi.bill_id
        JOIN   items      i ON i.id = bi.item_id
        JOIN   stores     s ON s.id = b.store_id
        WHERE  i.name LIKE ?
        GROUP  BY month, s.name
        ORDER  BY month
    """, (f"%{item_name}%",))


def inflation_summary() -> pd.DataFrame:
    """
    For each item that appears in ≥2 months, compute price change %.
    Returns items sorted by biggest price increase.
    """
    return _q("""
        WITH monthly_avg AS (
            SELECT i.name                              AS item,
                   strftime('%Y-%m', b.purchase_date)  AS month,
                   AVG(bi.price)                       AS avg_price
            FROM   bill_items bi
            JOIN   bills      b ON b.id = bi.bill_id
            JOIN   items      i ON i.id = bi.item_id
            GROUP  BY i.name, month
        ),
        ranked AS (
            SELECT item, month, avg_price,
                   ROW_NUMBER() OVER (PARTITION BY item ORDER BY month ASC)  AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY item ORDER BY month DESC) AS rn_last,
                   COUNT(*) OVER (PARTITION BY item)                         AS appearances
            FROM   monthly_avg
        )
        SELECT  f.item,
                f.month                                           AS first_month,
                l.month                                           AS last_month,
                ROUND(f.avg_price, 2)                            AS first_price,
                ROUND(l.avg_price, 2)                            AS last_price,
                ROUND((l.avg_price - f.avg_price) / f.avg_price * 100, 1) AS pct_change
        FROM    ranked f
        JOIN    ranked l ON f.item = l.item
        WHERE   f.rn_first = 1 AND l.rn_last = 1
          AND   f.appearances >= 2
        ORDER   BY pct_change DESC
    """)


def all_tracked_items() -> list:
    df = _q("SELECT DISTINCT name FROM items ORDER BY name")
    return df["name"].tolist()


# ── Smart tips ────────────────────────────────────────────────────────────────

def cheapest_store_per_item() -> pd.DataFrame:
    """For each item, find the store where it was cheapest on average."""
    return _q("""
        SELECT i.name               AS item,
               s.name               AS cheapest_store,
               ROUND(MIN(avg_p), 2) AS avg_price
        FROM (
            SELECT bi.item_id, b.store_id, AVG(bi.price) AS avg_p
            FROM   bill_items bi
            JOIN   bills      b ON b.id = bi.bill_id
            GROUP  BY bi.item_id, b.store_id
        ) sub
        JOIN items  i ON i.id = sub.item_id
        JOIN stores s ON s.id = sub.store_id
        GROUP BY i.name
        ORDER BY i.name
    """)


def overspend_alerts(threshold: float = 1.5) -> pd.DataFrame:
    """
    Items whose latest price is ≥ threshold × their historical average.
    Default: flag items that jumped 50% above their own average.
    """
    return _q("""
        WITH item_stats AS (
            SELECT i.name                              AS item,
                   AVG(bi.price)                       AS hist_avg,
                   MAX(b.purchase_date)                AS last_date
            FROM   bill_items bi
            JOIN   bills      b ON b.id = bi.bill_id
            JOIN   items      i ON i.id = bi.item_id
            GROUP  BY i.name
        ),
        latest_price AS (
            SELECT i.name AS item, bi.price
            FROM   bill_items bi
            JOIN   bills      b  ON b.id = bi.bill_id
            JOIN   items      i  ON i.id = bi.item_id
            WHERE  b.purchase_date = (
                SELECT MAX(b2.purchase_date)
                FROM   bill_items bi2
                JOIN   bills      b2 ON b2.id = bi2.bill_id
                JOIN   items      i2 ON i2.id = bi2.item_id
                WHERE  i2.name = i.name
            )
        )
        SELECT  s.item,
                ROUND(s.hist_avg, 2)             AS historical_avg,
                ROUND(l.price, 2)                AS latest_price,
                ROUND((l.price / s.hist_avg - 1) * 100, 1) AS pct_above_avg
        FROM    item_stats   s
        JOIN    latest_price l ON l.item = s.item
        WHERE   l.price >= s.hist_avg * ?
        ORDER   BY pct_above_avg DESC
    """, (threshold,))


def month_comparison(month_a: str, month_b: str) -> pd.DataFrame:
    """Compare total spending per category between two months."""
    return _q("""
        SELECT c.name AS category,
               ROUND(SUM(CASE WHEN strftime('%Y-%m', b.purchase_date)=? THEN bi.price*bi.quantity ELSE 0 END),2) AS month_a,
               ROUND(SUM(CASE WHEN strftime('%Y-%m', b.purchase_date)=? THEN bi.price*bi.quantity ELSE 0 END),2) AS month_b
        FROM   bill_items bi
        JOIN   bills      b  ON b.id  = bi.bill_id
        JOIN   items      i  ON i.id  = bi.item_id
        JOIN   categories c  ON c.id  = i.category_id
        WHERE  strftime('%Y-%m', b.purchase_date) IN (?,?)
        GROUP  BY c.name
    """, (month_a, month_b, month_a, month_b))


def get_all_months() -> list:
    df = _q("""
        SELECT DISTINCT strftime('%Y-%m', purchase_date) AS month
        FROM   bills
        ORDER  BY month
    """)
    return df["month"].tolist()

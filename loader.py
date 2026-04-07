"""
loader.py  –  Insert a parsed DataFrame into the SQLite database.
"""

import pandas as pd
from .database import get_connection


def upsert_store(cur, name: str, city: str = "", chain: str = "") -> int:
    cur.execute(
        "INSERT OR IGNORE INTO stores(name, city, chain) VALUES (?,?,?)",
        (name.strip().title(), city, chain)
    )
    cur.execute("SELECT id FROM stores WHERE name=? AND city=?", (name.strip().title(), city))
    return cur.fetchone()[0]


def upsert_category(cur, name: str, parent: str = None) -> int:
    cur.execute(
        "INSERT OR IGNORE INTO categories(name, parent_category) VALUES (?,?)",
        (name, parent)
    )
    cur.execute("SELECT id FROM categories WHERE name=?", (name,))
    return cur.fetchone()[0]


def upsert_item(cur, name: str, brand: str, unit: str, category_id: int) -> int:
    cur.execute(
        "INSERT OR IGNORE INTO items(name, brand, unit, category_id) VALUES (?,?,?,?)",
        (name, brand, unit, category_id)
    )
    cur.execute("SELECT id FROM items WHERE name=? AND brand=?", (name, brand))
    return cur.fetchone()[0]


def load_dataframe(df: pd.DataFrame, store_name: str, city: str,
                   purchase_date: str, source_file: str,
                   upload_method: str = "csv") -> int:
    """
    Insert all rows from df into the database.
    Returns the new bill_id.
    """
    conn = get_connection()
    cur  = conn.cursor()

    store_id    = upsert_store(cur, store_name, city)
    total_amount = (df["price"] * df["quantity"] - df["discount"]).sum()

    cur.execute(
        """INSERT INTO bills(store_id, purchase_date, total_amount, source_file, upload_method)
           VALUES (?,?,?,?,?)""",
        (store_id, purchase_date, round(total_amount, 2), source_file, upload_method)
    )
    bill_id = cur.lastrowid

    for _, row in df.iterrows():
        cat_id  = upsert_category(cur, row["category"])
        item_id = upsert_item(cur, row["item"], str(row.get("brand", "")),
                              str(row.get("unit", "")), cat_id)
        cur.execute(
            """INSERT INTO bill_items(bill_id, item_id, price, quantity, discount)
               VALUES (?,?,?,?,?)""",
            (bill_id, item_id, float(row["price"]), float(row["quantity"]),
             float(row.get("discount", 0)))
        )

    conn.commit()
    conn.close()
    return bill_id

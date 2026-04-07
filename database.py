import sqlite3
import os
import tempfile

# Streamlit Cloud has a writable /tmp directory — use it for the DB
# Locally it will also work fine
DB_PATH = os.path.join(tempfile.gettempdir(), "martmind_grocery.db")


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    cur  = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT NOT NULL,
            city  TEXT,
            chain TEXT,
            UNIQUE(name, city)
        );

        CREATE TABLE IF NOT EXISTS categories (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            parent_category TEXT
        );

        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            brand       TEXT,
            unit        TEXT,
            category_id INTEGER REFERENCES categories(id),
            UNIQUE(name, brand)
        );

        CREATE TABLE IF NOT EXISTS bills (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id      INTEGER REFERENCES stores(id),
            purchase_date TEXT NOT NULL,
            total_amount  REAL,
            source_file   TEXT,
            upload_method TEXT DEFAULT 'csv'
        );

        CREATE TABLE IF NOT EXISTS bill_items (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id  INTEGER REFERENCES bills(id),
            item_id  INTEGER REFERENCES items(id),
            price    REAL NOT NULL,
            quantity REAL DEFAULT 1,
            discount REAL DEFAULT 0
        );
    """)

    _seed_categories(cur)
    conn.commit()
    conn.close()


def _seed_categories(cur):
    cats = [
        ("Dairy & Eggs",      "Food"),
        ("Vegetables",        "Food"),
        ("Fruits",            "Food"),
        ("Grains & Pulses",   "Food"),
        ("Snacks",            "Food"),
        ("Beverages",         "Food"),
        ("Meat & Seafood",    "Food"),
        ("Oils & Condiments", "Food"),
        ("Cleaning",          "Household"),
        ("Personal Care",     "Household"),
        ("Other",             None),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO categories(name, parent_category) VALUES (?,?)",
        cats
    )

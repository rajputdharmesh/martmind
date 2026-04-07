"""
parser.py  –  Extract raw rows from PDF bills or CSV files.

PDF expected format (text-based, not scanned):
    Item Name   Qty   Price
    Tata Salt    1    22.00
    ...
    Total              342.50

CSV expected columns (flexible):
    item, quantity, price, date, store   (case-insensitive, extra cols ignored)
"""

import re
import io
import pandas as pd

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


# ── keywords that auto-assign a category ─────────────────────────────────────
CATEGORY_KEYWORDS = {
    "Dairy & Eggs":      ["milk", "curd", "paneer", "butter", "ghee", "cheese", "egg", "yogurt", "dahi"],
    "Vegetables":        ["onion", "potato", "tomato", "carrot", "spinach", "brinjal", "cabbage",
                          "capsicum", "beans", "peas", "lady", "bitter", "gourd"],
    "Fruits":            ["apple", "banana", "mango", "orange", "grapes", "watermelon", "papaya",
                          "lemon", "pomegranate", "guava"],
    "Grains & Pulses":   ["rice", "wheat", "atta", "dal", "lentil", "chana", "moong", "rajma",
                          "flour", "suji", "maida", "poha", "oats"],
    "Snacks":            ["biscuit", "chips", "namkeen", "kurkure", "maggi", "noodle", "bread",
                          "cake", "cookie", "rusk", "papad"],
    "Beverages":         ["tea", "coffee", "juice", "cold drink", "water", "soda", "lassi",
                          "milk shake", "horlicks", "bournvita"],
    "Oils & Condiments": ["oil", "salt", "sugar", "spice", "masala", "sauce", "ketchup", "pickle",
                          "vinegar", "mustard", "haldi", "jeera", "pepper"],
    "Cleaning":          ["soap", "detergent", "shampoo", "wash", "clean", "surf", "rin", "vim",
                          "harpic", "phenyl", "broom", "floor"],
    "Personal Care":     ["toothpaste", "brush", "deo", "deodorant", "cream", "lotion", "face",
                          "hair", "nail", "razor", "sanitary", "pad"],
    "Meat & Seafood":    ["chicken", "mutton", "fish", "prawn", "egg", "beef", "pork"],
}


def guess_category(item_name: str) -> str:
    name_lower = item_name.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return cat
    return "Other"


def normalize_item_name(name: str) -> str:
    """Title-case, strip extra spaces, remove special characters."""
    name = re.sub(r"[^a-zA-Z0-9\s\-&]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.title()


# ── CSV parser ────────────────────────────────────────────────────────────────

def parse_csv(file_obj, store_name: str, purchase_date: str) -> pd.DataFrame:
    """
    Accepts a file-like object.  Returns a cleaned DataFrame with columns:
    [item, quantity, price, discount, store, date, category, brand]
    """
    df = pd.read_csv(file_obj)
    df.columns = [c.strip().lower() for c in df.columns]

    col_map = {}
    for col in df.columns:
        if col in ("item", "item name", "name", "product", "description"):
            col_map["item"] = col
        elif col in ("qty", "quantity", "units", "pcs"):
            col_map["quantity"] = col
        elif col in ("price", "amount", "rate", "cost", "mrp", "total"):
            col_map["price"] = col
        elif col in ("discount", "disc", "offer"):
            col_map["discount"] = col
        elif col in ("brand",):
            col_map["brand"] = col
        elif col in ("date", "purchase_date", "bill_date"):
            col_map["date"] = col
        elif col in ("store", "shop", "store_name"):
            col_map["store"] = col

    if "item" not in col_map or "price" not in col_map:
        raise ValueError("CSV must have at least 'item' and 'price' columns.")

    result = pd.DataFrame()
    result["item"]     = df[col_map["item"]].astype(str).apply(normalize_item_name)
    result["price"]    = pd.to_numeric(df[col_map["price"]], errors="coerce").fillna(0)
    result["quantity"] = pd.to_numeric(df.get(col_map.get("quantity", ""), 1), errors="coerce").fillna(1)
    result["discount"] = pd.to_numeric(df.get(col_map.get("discount", ""), 0), errors="coerce").fillna(0)
    result["brand"]    = df[col_map["brand"]].astype(str).str.title() if "brand" in col_map else ""
    result["store"]    = df[col_map["store"]].astype(str) if "store" in col_map else store_name
    result["date"]     = df[col_map["date"]].astype(str) if "date" in col_map else purchase_date
    result["category"] = result["item"].apply(guess_category)

    result = result[result["price"] > 0].reset_index(drop=True)
    return result


# ── PDF parser ────────────────────────────────────────────────────────────────

def parse_pdf(file_obj, store_name: str, purchase_date: str) -> pd.DataFrame:
    if not PDF_SUPPORT:
        raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")

    rows = []
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            # Try structured table extraction first
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        row = [str(c).strip() if c else "" for c in row]
                        item, qty, price = _try_parse_row(row)
                        if item and price:
                            rows.append((item, qty, price))
            else:
                # Fallback: parse raw text line by line
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    # Last token is likely price
                    try:
                        price_val = float(parts[-1].replace(",", ""))
                        qty_val   = float(parts[-2]) if len(parts) > 2 else 1
                        # item name is everything before qty and price
                        name_end  = -2 if len(parts) > 2 else -1
                        item_name = " ".join(parts[:name_end])
                        if item_name and price_val > 0:
                            rows.append((item_name, qty_val, price_val))
                    except ValueError:
                        continue

    if not rows:
        raise ValueError("Could not extract any items from the PDF. Make sure it is text-based (not scanned).")

    df = pd.DataFrame(rows, columns=["item", "quantity", "price"])
    df["item"]     = df["item"].apply(normalize_item_name)
    df["discount"] = 0.0
    df["brand"]    = ""
    df["store"]    = store_name
    df["date"]     = purchase_date
    df["category"] = df["item"].apply(guess_category)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


def _try_parse_row(row):
    """Try to extract (item, qty, price) from a table row."""
    try:
        price = float(str(row[-1]).replace(",", "").replace("₹", "").strip())
        qty   = float(str(row[-2]).replace(",", "").strip()) if len(row) > 2 else 1.0
        item  = " ".join(str(c) for c in row[:-2]).strip() if len(row) > 2 else str(row[0]).strip()
        if not item or price <= 0:
            return None, None, None
        return item, qty, price
    except (ValueError, IndexError):
        return None, None, None

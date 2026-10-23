# init_db.py: INITIALIZES & SEEDS supermarket_meta.db WITH ALL 36 PRODUCE CLASSES (₹)
# Run once:  python init_db.py
# PRODUCE_SEED_DATA is also imported by decision_engine.py as its offline
# fallback, so the DB and the fallback can never drift apart.
#
# Prices are Indian rupees PER UNIT COUNTED by the camera:
#   * per piece for large produce (apple, mango, cabbage, watermelon...)
#   * per pack/bunch for small produce sold that way (peas 250 g, chillies 100 g,
#     garlic 100 g, ginger 100 g, grapes 500 g, spinach bunch...)
# Illustrative retail-style demo prices, not live market rates.
# A small `db_meta` table records the currency so an old dollar database is
# detected and reseeded automatically (decision_engine.py).
import sqlite3
from pathlib import Path

from config import CURRENCY_CODE, DB_PATH

SEED_VERSION = "2026-10-inr-v1"

# Format: (product_type, base_price ₹, cost_price ₹, max_discount_pct, target_capacity, price_elasticity)
PRODUCE_SEED_DATA = [
    ("Apple",          36.00, 18.00, 0.50, 20, 1.50),   # per piece
    ("Banana",          7.00,  2.50, 0.60, 40, 2.50),   # per piece
    ("Beetroot",       12.00,  5.50, 0.40, 25, 1.15),   # per piece
    ("Bell Pepper",    45.00, 21.00, 0.45, 25, 1.60),   # per piece (coloured)
    ("Cabbage",        35.00, 14.00, 0.40, 15, 1.30),   # per head
    ("Capsicum",       15.00,  7.00, 0.45, 25, 1.55),   # per piece (green)
    ("Carrot",          8.00,  3.50, 0.40, 35, 1.70),   # per piece
    ("Cauliflower",    40.00, 17.00, 0.45, 15, 1.40),   # per head
    ("Chilli Pepper",  12.00,  4.00, 0.35, 50, 1.10),   # per 100 g pack
    ("Corn",           25.00, 11.00, 0.45, 30, 1.65),   # per cob
    ("Cucumber",       10.00,  4.00, 0.45, 30, 1.80),   # per piece
    ("Eggplant",       15.00,  6.50, 0.45, 20, 1.35),   # per piece
    ("Garlic",         30.00, 12.00, 0.30, 45, 1.05),   # per 100 g pack
    ("Ginger",         20.00,  8.50, 0.30, 40, 1.10),   # per 100 g pack
    ("Grapes",         60.00, 29.00, 0.55, 20, 2.10),   # per 500 g pack
    ("Jalepeno",       25.00, 10.00, 0.35, 45, 1.15),   # per 100 g pack
    ("Kiwi",           25.00, 12.50, 0.50, 25, 1.75),   # per piece
    ("Lemon",           5.00,  2.00, 0.40, 45, 1.45),   # per piece
    ("Lettuce",        60.00, 25.00, 0.55, 20, 1.90),   # per head
    ("Mango",          50.00, 24.00, 0.50, 20, 2.20),   # per piece
    ("Onion",           6.00,  2.50, 0.35, 40, 1.25),   # per piece
    ("Orange",         15.00,  7.50, 0.50, 15, 1.20),   # per piece
    ("Paprika",        40.00, 18.50, 0.40, 25, 1.30),   # per piece
    ("Pear",           30.00, 14.50, 0.50, 20, 1.60),   # per piece
    ("Peas",           30.00, 13.50, 0.45, 30, 1.50),   # per 250 g pack
    ("Pineapple",      80.00, 38.00, 0.50, 12, 1.85),   # per piece
    ("Pomegranate",    45.00, 21.00, 0.45, 18, 1.65),   # per piece
    ("Potato",          6.00,  2.50, 0.35, 50, 1.30),   # per piece
    ("Raddish",        10.00,  4.00, 0.40, 30, 1.20),   # per piece
    ("Soy Beans",      35.00, 15.00, 0.40, 30, 1.25),   # per 250 g pack
    ("Spinach",        25.00, 10.00, 0.60, 25, 2.00),   # per bunch
    ("Sweetcorn",      30.00, 13.00, 0.45, 30, 1.70),   # per cob
    ("Sweetpotato",    15.00,  6.50, 0.35, 35, 1.35),   # per piece
    ("Tomato",          6.00,  2.50, 0.40, 30, 2.00),   # per piece
    ("Turnip",         10.00,  4.00, 0.40, 25, 1.15),   # per piece
    ("Watermelon",     70.00, 33.00, 0.50, 10, 2.10),   # per piece
]


def initialize_database(db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 1. Produce metadata table (the 6 attributes from CLAUDE.md §3B)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produce_pricing_meta (
                product_type      VARCHAR(50) PRIMARY KEY,
                base_price        DECIMAL(6, 2) NOT NULL CHECK (base_price > 0),
                cost_price        DECIMAL(6, 2) NOT NULL CHECK (cost_price > 0 AND cost_price <= base_price),
                max_discount_pct  FLOAT NOT NULL CHECK (max_discount_pct >= 0.0 AND max_discount_pct <= 0.90),
                target_capacity   INT NOT NULL CHECK (target_capacity > 0),
                price_elasticity  FLOAT NOT NULL CHECK (price_elasticity > 0.0)
            );
        """)

        # 2. Upsert all 36 classes in a single transaction
        cursor.executemany("""
            INSERT OR REPLACE INTO produce_pricing_meta (
                product_type, base_price, cost_price, max_discount_pct, target_capacity, price_elasticity
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, PRODUCE_SEED_DATA)

        # 3. Database-level metadata: which currency the prices are in
        cursor.execute("CREATE TABLE IF NOT EXISTS db_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        cursor.executemany("INSERT OR REPLACE INTO db_meta (key, value) VALUES (?, ?);",
                           [("currency", CURRENCY_CODE), ("seed_version", SEED_VERSION)])
        conn.commit()

    print(f"[OK] Database initialized at '{Path(db_path).resolve()}' with {len(PRODUCE_SEED_DATA)} "
          f"produce classes (prices in {CURRENCY_CODE}).")


def database_currency(db_path: Path = DB_PATH):
    """Currency code stored in the DB, or None for a pre-rupee (dollar) database."""
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM db_meta WHERE key = 'currency'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


if __name__ == "__main__":
    initialize_database()

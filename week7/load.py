import sqlite3
import polars as pl
from datetime import datetime

DDL = """
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  TEXT UNIQUE NOT NULL,
    customer_name TEXT,
    province TEXT,
    segment TEXT
);
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT UNIQUE NOT NULL,
    product_name TEXT,
    category TEXT
);
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT UNIQUE NOT NULL,
    day INTEGER,
    month INTEGER,
    quarter INTEGER,
    year INTEGER
);
CREATE TABLE IF NOT EXISTS fact_sales (
    fact_key INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    discount_pct REAL NOT NULL CHECK (discount_pct BETWEEN 0 AND 100),
    gross_amount REAL NOT NULL CHECK (gross_amount >= 0),
    net_amount REAL NOT NULL CHECK (net_amount >= 0),
    payment_method TEXT,
    sales_channel TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_key INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    source_batch TEXT,
    reason_code TEXT,
    raw_payload TEXT,
    loaded_at TEXT
);
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    run_key INTEGER PRIMARY KEY AUTOINCREMENT,
    batch TEXT,
    started_at TEXT,
    ended_at TEXT,
    rows_read INTEGER,
    rows_valid INTEGER,
    rows_loaded INTEGER,
    rows_rejected INTEGER,
    rows_duplicated INTEGER,
    status TEXT
);
"""

def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(DDL)
    conn.commit()

def load_dimensions(conn: sqlite3.Connection, customers: pl.DataFrame, products: pl.DataFrame):
    cur = conn.cursor()
    for r in customers.iter_rows(named=True):
        cur.execute(
            """INSERT INTO dim_customer (customer_id, customer_name, province, segment)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(customer_id) DO UPDATE SET
                 customer_name=excluded.customer_name,
                 province=excluded.province,
                 segment=excluded.segment""",
            (r["customer_id"], r["customer_name"], r["province"], r["segment"]),
        )
    for r in products.iter_rows(named=True):
        cur.execute(
            """INSERT INTO dim_product (product_id, product_name, category)
               VALUES (?, ?, ?)
               ON CONFLICT(product_id) DO UPDATE SET
                 product_name=excluded.product_name,
                 category=excluded.category""",
            (r["product_id"], r["product_name"], r["category"]),
        )
    conn.commit()

def get_or_create_date_key(cur: sqlite3.Cursor, ts) -> int:
    full_date = ts.strftime("%Y-%m-%d")
    date_key = int(ts.strftime("%Y%m%d"))
    cur.execute(
        """INSERT INTO dim_date (date_key, full_date, day, month, quarter, year)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(date_key) DO NOTHING""",
        (date_key, full_date, ts.day, ts.month, (ts.month - 1) // 3 + 1, ts.year),
    )
    return date_key

def load_facts(conn: sqlite3.Connection, clean: pl.DataFrame) -> tuple[int, int]:
    cur = conn.cursor()
    loaded = 0
    for r in clean.iter_rows(named=True):
        date_key = get_or_create_date_key(cur, r["order_datetime_parsed"])
        cur.execute("SELECT customer_key FROM dim_customer WHERE customer_id=?", (r["customer_id"],))
        cust_row = cur.fetchone()
        cur.execute("SELECT product_key FROM dim_product WHERE product_id=?", (r["product_id"],))
        prod_row = cur.fetchone()
        
        if not cust_row or not prod_row:
            continue
            
        cur.execute(
            """INSERT INTO fact_sales
               (order_id, date_key, customer_key, product_key, quantity, unit_price,
                discount_pct, gross_amount, net_amount, payment_method, sales_channel, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(order_id) DO UPDATE SET
                 date_key=excluded.date_key,
                 customer_key=excluded.customer_key,
                 product_key=excluded.product_key,
                 quantity=excluded.quantity,
                 unit_price=excluded.unit_price,
                 discount_pct=excluded.discount_pct,
                 gross_amount=excluded.gross_amount,
                 net_amount=excluded.net_amount,
                 payment_method=excluded.payment_method,
                 sales_channel=excluded.sales_channel,
                 updated_at=excluded.updated_at
               WHERE excluded.updated_at > fact_sales.updated_at""",
            (
                r["order_id"], date_key, cust_row[0], prod_row[0],
                int(r["quantity_num"]), float(r["unit_price_num"]), float(r["discount_pct_num"]),
                float(r["gross_amount"]), float(r["net_amount"]),
                r["payment_method_norm"], r["sales_channel_norm"],
                r["updated_at_parsed"].isoformat(),
            ),
        )
        loaded += 1
    conn.commit()
    return loaded, 0

def load_quarantine(conn: sqlite3.Connection, quarantine: pl.DataFrame):
    if quarantine.is_empty(): return
    cur = conn.cursor()
    now = datetime.now().isoformat()
    for r in quarantine.iter_rows(named=True):
        payload_cols = ["order_id", "order_datetime", "customer_id", "product_id", "quantity",
                         "unit_price", "discount_pct", "payment_method", "sales_channel", "updated_at"]
        payload = "; ".join(f"{c}={r.get(c)}" for c in payload_cols)
        cur.execute(
            """INSERT INTO quarantine (order_id, source_batch, reason_code, raw_payload, loaded_at)
               VALUES (?, ?, ?, ?, ?)""",
            (r.get("order_id"), r.get("source_batch"), r.get("reason_code"), payload, now),
        )
    conn.commit()

def write_run_log(conn: sqlite3.Connection, batch, started, ended, rows_read, rows_valid,
                   rows_loaded, rows_rejected, rows_duplicated, status):
    conn.execute(
        """INSERT INTO pipeline_run_log
           (batch, started_at, ended_at, rows_read, rows_valid, rows_loaded,
            rows_rejected, rows_duplicated, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (batch, started.isoformat(), ended.isoformat(), rows_read, rows_valid,
         rows_loaded, rows_rejected, rows_duplicated, status),
    )
    conn.commit()

def get_watermark(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        cur = conn.execute("SELECT order_id, updated_at FROM fact_sales")
        return {r[0]: r[1] for r in cur.fetchall()}
    except sqlite3.OperationalError:
        return {}
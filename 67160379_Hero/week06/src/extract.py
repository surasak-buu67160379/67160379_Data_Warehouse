import json
import sqlite3
import pandas as pd
from .config import RAW_DIR, SOURCE_DB

def extract_data():
    """
    Extract data from raw directory and source database:
      - customers.csv
      - orders.csv
      - products.json (flatten using pd.json_normalize)
      - stores table in store.db
    
    Returns:
        dict: Dictionary containing DataFrames for customers, orders, products, and stores.
    """
    # 1. อ่านไฟล์ customers.csv
    customers_df = pd.read_csv(RAW_DIR / "customers.csv")

    # 2. อ่านไฟล์ orders.csv
    orders_df = pd.read_csv(RAW_DIR / "orders.csv")

    # 3. อ่านไฟล์ products.json และ flatten nested JSON ด้วย pd.json_normalize()
    with open(RAW_DIR / "products.json", "r", encoding="utf-8") as f:
        products_data = json.load(f)
    products_df = pd.json_normalize(products_data)

    # 4. อ่านตาราง stores จากฐานข้อมูล SQLite (SOURCE_DB)
    conn = sqlite3.connect(SOURCE_DB)
    stores_df = pd.read_sql_query("SELECT * FROM stores", conn)
    conn.close()

    # คืนค่าเป็น Dictionary ของ DataFrames ตามโจทย์กำหนด
    return {
        "customers": customers_df,
        "orders": orders_df,
        "products": products_df,
        "stores": stores_df,
    }
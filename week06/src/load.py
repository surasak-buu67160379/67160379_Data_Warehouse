import sqlite3
from .config import WAREHOUSE_DB

def load_data(clean_customers, clean_products, sales):
    """
    Part 3: Load
    โหลดข้อมูลเข้า SQLite Warehouse (data/warehouse/warehouse.db)
    สร้าง 3 ตาราง: dim_customer, dim_product, fact_sales
    ใช้ INSERT OR REPLACE เพื่อรองรับการ rerun โดยไม่เกิด order_id ซ้ำ
    """
    # สร้างโฟลเดอร์ปลายทางถ้ายังไม่มี
    WAREHOUSE_DB.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(WAREHOUSE_DB)
    cursor = conn.cursor()

    # 1. สร้าง Schema ของตารางทั้ง 3
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        province TEXT,
        email TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_product (
        product_id TEXT PRIMARY KEY,
        product_name TEXT,
        category TEXT,
        price REAL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_sales (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT,
        product_id TEXT,
        order_date TEXT,
        qty INTEGER,
        unit_price REAL,
        discount_pct REAL,
        sales_amount REAL
    );
    """)
    conn.commit()

    # 2. โหลดข้อมูลเข้า dim_customer
    cust_df = clean_customers[["customer_id", "name", "province", "email"]]
    cursor.executemany("""
    INSERT OR REPLACE INTO dim_customer (customer_id, name, province, email)
    VALUES (:customer_id, :name, :province, :email)
    """, cust_df.to_dict(orient="records"))

    # 3. โหลดข้อมูลเข้า dim_product
    prod_df = clean_products[["product_id", "product_name", "category", "price"]]
    cursor.executemany("""
    INSERT OR REPLACE INTO dim_product (product_id, product_name, category, price)
    VALUES (:product_id, :product_name, :category, :price)
    """, prod_df.to_dict(orient="records"))

    # 4. โหลดข้อมูลเข้า fact_sales (ป้องกัน duplicate order_id เมื่อ rerun)
    fact_cols = ["order_id", "customer_id", "product_id", "order_date", "qty", "unit_price", "discount_pct", "sales_amount"]
    sales_df = sales[fact_cols]
    cursor.executemany("""
    INSERT OR REPLACE INTO fact_sales (order_id, customer_id, product_id, order_date, qty, unit_price, discount_pct, sales_amount)
    VALUES (:order_id, :customer_id, :product_id, :order_date, :qty, :unit_price, :discount_pct, :sales_amount)
    """, sales_df.to_dict(orient="records"))

    conn.commit()
    conn.close()
    print("📦 [LOAD] Data successfully loaded into SQLite Warehouse.")
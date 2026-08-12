import json
import sqlite3
from .config import WAREHOUSE_DB, OUTPUT_DIR

def validate_data(sales_df):
    """
    Part 4: Validate
    ตรวจสอบความถูกต้อง เปรียบเทียบข้อมูลก่อนและหลัง Load เข้า Warehouse
    สร้างไฟล์ output/validation.json
    """
    conn = sqlite3.connect(WAREHOUSE_DB)
    cursor = conn.cursor()

    # ดึงค่าสรุปจาก SQLite Warehouse
    cursor.execute("SELECT COUNT(*), COUNT(DISTINCT order_id), SUM(sales_amount) FROM fact_sales")
    wh_count, wh_unique, wh_sales_sum = cursor.fetchone()
    conn.close()

    source_rows = len(sales_df)
    source_sales = round(float(sales_df["sales_amount"].sum()), 2)
    wh_sales = round(float(wh_sales_sum or 0), 2)
    duplicates = wh_count - wh_unique

    # ตรวจสอบสถานะ
    status = "PASS" if (source_rows == wh_count and duplicates == 0 and abs(source_sales - wh_sales) < 0.01) else "FAIL"

    metrics = {
        "source_valid_rows": source_rows,
        "warehouse_rows": wh_count,
        "duplicate_order_ids": duplicates,
        "source_total_sales": source_sales,
        "warehouse_total_sales": wh_sales,
        "status": status
    }

    # บันทึกเป็นไฟล์ validation.json
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "validation.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)

    print("📊 [VALIDATE] Validation Metrics:")
    print(json.dumps(metrics, indent=4))
    
    return metrics
import sqlite3
import polars as pl
from datetime import datetime
from pathlib import Path

from config import PipelineConfig, log
from extract import extract
from transform import transform
from load import (ensure_schema, load_dimensions, load_facts, 
                  load_quarantine, write_run_log, get_watermark)

def run_pipeline(config: PipelineConfig, batch: str) -> dict:
    started = datetime.now()
    log.info(f"=== RUN START batch={batch} ===")
    conn = sqlite3.connect(config.output_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)

    status = "success"
    rows_read = rows_valid = rows_loaded = rows_rejected = rows_dup = 0
    try:
        customers, products, orders = extract(config, batch)
        load_dimensions(conn, customers, products)

        watermark = get_watermark(conn)
        clean, quarantine, rows_read, skipped = transform(orders, customers, products, watermark, batch)

        # Polars ใช้ .height แทน len()
        rows_valid = clean.height + skipped.height
        rows_rejected = quarantine.height
        
        if not quarantine.is_empty():
            rows_dup = quarantine.filter(pl.col("reason_code") == "duplicate_order_id_superseded").height
        else:
            rows_dup = 0

        loaded, _ = load_facts(conn, clean)
        rows_loaded = loaded
        load_quarantine(conn, quarantine)

        log.info(f"TRANSFORM {batch}: read={rows_read} valid={rows_valid} "
                 f"rejected={rows_rejected} skipped_already_loaded={skipped.height}")
        log.info(f"LOAD {batch}: loaded={rows_loaded} quarantined={rows_rejected}")
    except Exception as exc:
        status = "failed"
        log.error(f"RUN {batch}: FAILED - {exc} (previously loaded data left intact)")
        conn.rollback()
    finally:
        ended = datetime.now()
        write_run_log(conn, batch, started, ended, rows_read, rows_valid, rows_loaded,
                      rows_rejected, rows_dup, status)
        conn.close()

    log.info(f"=== RUN END batch={batch} status={status} "
             f"read={rows_read} loaded={rows_loaded} rejected={rows_rejected} ===\n")
    return dict(batch=batch, status=status, rows_read=rows_read, rows_valid=rows_valid,
                rows_loaded=rows_loaded, rows_rejected=rows_rejected, rows_duplicated=rows_dup)

def export_quarantine_csv(config: PipelineConfig):
    conn = sqlite3.connect(config.output_db)
    # ใช้ read_database ของ Polars ได้เลย
    df = pl.read_database("SELECT * FROM quarantine", connection=conn)
    conn.close()
    config.quarantine_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(config.quarantine_csv)
    return df

def export_run_log_csv(config: PipelineConfig):
    conn = sqlite3.connect(config.output_db)
    df = pl.read_database("SELECT * FROM pipeline_run_log", connection=conn)
    conn.close()
    config.run_log_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(config.run_log_csv)
    return df

def kpi_summary(config: PipelineConfig):
    conn = sqlite3.connect(config.output_db)
    fact_count = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    net_sum = conn.execute("SELECT COALESCE(SUM(net_amount),0) FROM fact_sales").fetchone()[0]
    quarantine_count = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    conn.close()
    return dict(fact_rows=fact_count, total_net_sales=round(net_sum, 2), quarantined_rows=quarantine_count)

if __name__ == "__main__":
    config = PipelineConfig(
        # เติมคำว่า data/ นำหน้าชื่อไฟล์เข้าไปครับ
        input_path=Path("data/Python_Data_Pipeline_Lab_Dataset.xlsx"), 
        output_db=Path("output/retail_dw.db"),
        batches=["orders_batch_1", "orders_batch_2", "orders_batch_3"],
    )
    config.output_db.parent.mkdir(parents=True, exist_ok=True)

    if config.output_db.exists():
        config.output_db.unlink()

    results = []
    results.append(run_pipeline(config, "orders_batch_1"))
    results.append(run_pipeline(config, "orders_batch_1"))
    results.append(run_pipeline(config, "orders_batch_2"))
    results.append(run_pipeline(config, "orders_batch_3"))

    export_quarantine_csv(config)
    export_run_log_csv(config)

    print("\n=== RUN RESULTS ===")
    for r in results: print(r)

    print("\n=== KPI SUMMARY ===")
    print(kpi_summary(config))
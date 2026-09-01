import polars as pl
from datetime import datetime
from pathlib import Path
from config import PipelineConfig, log

def extract_table(path: Path, sheet_name: str) -> pl.DataFrame:
    started = datetime.now()
    try:
        # เปลี่ยน engine เป็น "openpyxl" ที่เราเพิ่งติดตั้งไปครับ
        df = pl.read_excel(
            source=path,
            sheet_name=sheet_name,
            engine="openpyxl", 
            infer_schema_length=0 
        )
        elapsed = (datetime.now() - started).total_seconds()
        log.info(f"EXTRACT {sheet_name}: rows={df.height} start={started:%H:%M:%S} elapsed={elapsed:.3f}s")
        return df
    except Exception as exc:
        log.error(f"EXTRACT {sheet_name}: FAILED ({exc})")
        raise

def extract(config: PipelineConfig, batch: str):
    customers = extract_table(config.input_path, "customers")
    products = extract_table(config.input_path, "products")
    orders = extract_table(config.input_path, batch)
    return customers, products, orders
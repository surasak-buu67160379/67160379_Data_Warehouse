import polars as pl

APPROVED_PAYMENT_METHODS = ["cash", "credit card", "bank transfer", "promptpay"]
SALES_CHANNEL_MAP = {
    "store": "Store",
    "online": "Online",
    "marketplace": "Marketplace",
    "e-commerce": "Online",
}

def transform(orders: pl.DataFrame, customers: pl.DataFrame, products: pl.DataFrame,
              already_loaded: dict[str, str], batch: str):
    rows_read = orders.height
    
    valid_customers = customers["customer_id"].drop_nulls().to_list()
    valid_products = products["product_id"].drop_nulls().to_list()

    # ---- 1. แปลง Data Type & ทำความสะอาดแบบรวดเดียว (Expressions) ----
    df = orders.with_columns(
        pl.lit(batch).alias("source_batch"),
        pl.col("order_datetime").str.to_datetime(strict=False).alias("order_datetime_parsed"),
        pl.col("updated_at").str.to_datetime(strict=False).alias("updated_at_parsed"),
        pl.col("quantity").str.strip_chars().cast(pl.Float64, strict=False).alias("quantity_num"),
        
        # ตัด THB และลูกน้ำออก แล้วค่อยแปลงเป็น Float
        pl.col("unit_price").str.to_uppercase().str.replace_all("THB", "").str.replace_all(",", "").str.strip_chars().cast(pl.Float64, strict=False).alias("unit_price_num"),
        pl.col("discount_pct").cast(pl.Float64, strict=False).alias("discount_pct_num"),
        pl.col("payment_method").str.strip_chars().str.to_lowercase().alias("_pm_lower")
    ).with_columns(
        # Map categorical
        pl.when(pl.col("_pm_lower").is_in(APPROVED_PAYMENT_METHODS))
          .then(pl.col("_pm_lower").str.to_titlecase())
          .otherwise(pl.lit(None)).alias("payment_method_norm"),
          
        pl.col("sales_channel").str.strip_chars().str.to_lowercase().replace(SALES_CHANNEL_MAP, default=None).alias("sales_channel_norm")
    )

    # ---- 2. สร้าง Boolean Flags ตรวจสอบความผิดปกติ ----
    df = df.with_columns(
        r_datetime = pl.col("order_datetime_parsed").is_null(),
        r_qty_type = pl.col("quantity_num").is_null(),
        r_qty_range = pl.col("quantity_num").is_not_null() & ((pl.col("quantity_num") <= 0) | (pl.col("quantity_num") > 20) | (pl.col("quantity_num") % 1 != 0)),
        r_price_type = pl.col("unit_price_num").is_null(),
        r_price_range = pl.col("unit_price_num").is_not_null() & (pl.col("unit_price_num") <= 0),
        r_disc_type = pl.col("discount_pct_num").is_null(),
        r_disc_range = pl.col("discount_pct_num").is_not_null() & ((pl.col("discount_pct_num") < 0) | (pl.col("discount_pct_num") > 100)),
        r_pm = pl.col("payment_method_norm").is_null(),
        r_sc = pl.col("sales_channel_norm").is_null(),
        r_cust = pl.col("customer_id").is_null() | ~pl.col("customer_id").is_in(valid_customers),
        r_prod = pl.col("product_id").is_null() | ~pl.col("product_id").is_in(valid_products),
        r_updated = pl.col("updated_at_parsed").is_null()
    )

    # ---- 3. แปลง Flags เป็น Reason Code แบบ String Concat ----
    reasons = [
        ("invalid_order_datetime", "r_datetime"), ("invalid_quantity_type", "r_qty_type"),
        ("quantity_out_of_range", "r_qty_range"), ("invalid_unit_price_type", "r_price_type"),
        ("unit_price_not_positive", "r_price_range"), ("invalid_discount_pct_type", "r_disc_type"),
        ("discount_pct_out_of_range", "r_disc_range"), ("invalid_payment_method", "r_pm"),
        ("invalid_sales_channel", "r_sc"), ("customer_id_not_found", "r_cust"),
        ("product_id_not_found", "r_prod"), ("invalid_updated_at", "r_updated")
    ]
    
    exprs = [
        pl.when(pl.col(col)).then(pl.lit(name + "|")).otherwise(pl.lit(""))
        for name, col in reasons
    ]
    df = df.with_columns(reason_code = pl.concat_str(exprs).str.strip_chars_end("|"))

    # ---- 4. แยกของดี ของเสีย ----
    row_valid = df.filter(pl.col("reason_code") == "")
    row_invalid = df.filter(pl.col("reason_code") != "")

    # ---- 5. Deduplicate (ออเดอร์ซ้ำใน Batch) ----
    row_valid = row_valid.sort("updated_at_parsed")
    row_valid_latest = row_valid.unique(subset=["order_id"], keep="last")
    
    duplicated_rows = row_valid.join(row_valid_latest, on=["order_id", "updated_at_parsed"], how="anti")
    duplicated_rows = duplicated_rows.with_columns(pl.lit("duplicate_order_id_superseded").alias("reason_code"))
    
    row_valid = row_valid_latest

    # ---- 6. Incremental Load (เทียบกับ DB) ----
    if already_loaded:
        loaded_df = pl.DataFrame(
            {"order_id": list(already_loaded.keys()), "prev_updated": list(already_loaded.values())}
        ).with_columns(pl.col("prev_updated").str.to_datetime(strict=False))
        
        row_valid = row_valid.join(loaded_df, on="order_id", how="left")
        is_new_or_updated = pl.col("prev_updated").is_null() | (pl.col("updated_at_parsed") > pl.col("prev_updated"))
        
        skipped_already_loaded = row_valid.filter(~is_new_or_updated)
        row_valid = row_valid.filter(is_new_or_updated)
    else:
        skipped_already_loaded = row_valid.clear()

    # ---- 7. คำนวณยอดเงิน (Derived Measures) ----
    row_valid = row_valid.with_columns(
        gross_amount = pl.col("quantity_num") * pl.col("unit_price_num")
    ).with_columns(
        net_amount = pl.col("gross_amount") * (1 - pl.col("discount_pct_num") / 100)
    )

    # รวมของเสียเข้าด้วยกัน
    quarantine = pl.concat([row_invalid, duplicated_rows], how="diagonal_relaxed")

    return row_valid, quarantine, rows_read, skipped_already_loaded
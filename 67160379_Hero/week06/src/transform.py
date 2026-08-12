import pandas as pd
from .config import PROVINCE_MAP, OUTPUT_DIR

def transform_data(raw):
    """
    Part 2: Transform
    - Clean Customers, Products, and Orders
    - Filter Invalid Records to Rejects
    - Merge with Masters & Calculate Sales
    """
    
    # ==========================================
    # 1. CUSTOMERS
    # ==========================================
    df_cust = raw["customers"].copy()
    df_cust = df_cust.drop_duplicates(subset=["customer_id"])
    
    if "province" in df_cust.columns:
        clean_prov = df_cust["province"].astype(str).str.strip().str.lower()
        df_cust["province"] = clean_prov.map(PROVINCE_MAP).fillna(df_cust["province"]).fillna("Unknown")
        
    if "email" in df_cust.columns:
        df_cust["email"] = df_cust["email"].fillna("unknown@example.com")
        
    clean_customers = df_cust

    # ==========================================
    # 2. PRODUCTS
    # ==========================================
    df_prod = raw["products"].copy()
    
    rename_dict = {}
    for col in df_prod.columns:
        col_str = str(col)
        col_lower = col_str.lower().strip()
        
        if "category" in col_lower or "cat" in col_lower:
            rename_dict[col] = "category"
        elif "price" in col_lower or "pricing" in col_lower:
            rename_dict[col] = "price"
        elif col_lower in ["product_id", "id", "prod_id"] or col_lower.endswith("product_id"):
            rename_dict[col] = "product_id"
        elif col_lower in ["product_name", "prod_name", "title"] or col_lower == "name":
            rename_dict[col] = "product_name"

    if rename_dict:
        df_prod = df_prod.rename(columns=rename_dict)
        
    df_prod = df_prod.loc[:, ~df_prod.columns.duplicated()]

    if "product_id" not in df_prod.columns:
        df_prod["product_id"] = df_prod.iloc[:, 0].astype(str)
    if "product_name" not in df_prod.columns:
        df_prod["product_name"] = "Unknown Product"
    if "price" not in df_prod.columns:
        df_prod["price"] = 0.0
    if "category" not in df_prod.columns:
        df_prod["category"] = "Unknown"

    df_prod["price"] = (
        df_prod["price"]
        .astype(str)
        .str.replace(",", "", regex=False)
    )
    df_prod["price"] = pd.to_numeric(df_prod["price"], errors="coerce").fillna(0.0)
    
    df_prod["category"] = df_prod["category"].fillna("Unknown").astype(str).str.strip()
    df_prod["category"] = df_prod["category"].replace(["", "nan", "None", "null"], "Unknown")

    clean_products = df_prod[["product_id", "product_name", "category", "price"]]

    # ==========================================
    # 3. ORDERS (ปรับการอ่านวันที่แบบ mixed format)
    # ==========================================
    df_orders = raw["orders"].copy()
    df_orders = df_orders.drop_duplicates(subset=["order_id"])
    
    # 🟢 เพิ่ม format="mixed" และ dayfirst=True
    df_orders["parsed_date"] = pd.to_datetime(
        df_orders["order_date"], 
        format="mixed", 
        dayfirst=True, 
        errors="coerce"
    )
    
    if "status" in df_orders.columns:
        df_orders["status"] = df_orders["status"].astype(str).str.lower().str.strip()

    # Reject Rules
    cond_invalid_qty = df_orders["qty"] <= 0
    cond_invalid_price = df_orders["unit_price"] <= 0
    cond_invalid_discount = (df_orders["discount_pct"] < 0) | (df_orders["discount_pct"] > 100)
    cond_invalid_date = df_orders["parsed_date"].isna()

    cond_rule_reject = cond_invalid_qty | cond_invalid_price | cond_invalid_discount | cond_invalid_date

    reject_rules_df = df_orders[cond_rule_reject].copy()
    reject_rules_df["reject_reason"] = "Invalid Record Rules"

    valid_orders = df_orders[~cond_rule_reject].copy()
    valid_orders["order_date"] = valid_orders["parsed_date"].dt.strftime("%Y-%m-%d")
    valid_orders = valid_orders.drop(columns=["parsed_date"])

    # ==========================================
    # 4. MERGE & FILTER STATUS & FOREIGN KEY CHECK
    # ==========================================
    valid_orders = valid_orders[valid_orders["status"].isin(["paid", "completed"])]
    
    valid_cust_ids = set(clean_customers["customer_id"])
    valid_prod_ids = set(clean_products["product_id"])

    cond_unknown_cust = ~valid_orders["customer_id"].isin(valid_cust_ids)
    cond_unknown_prod = ~valid_orders["product_id"].isin(valid_prod_ids)

    reject_fk_df = valid_orders[cond_unknown_cust | cond_unknown_prod].copy()
    reject_fk_df["reject_reason"] = "Unknown Customer ID or Product ID"

    rejects = pd.concat([reject_rules_df, reject_fk_df], ignore_index=True)
    if "parsed_date" in rejects.columns:
        rejects = rejects.drop(columns=["parsed_date"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rejects.to_csv(OUTPUT_DIR / "rejects.csv", index=False)

    # ==========================================
    # 5. CALCULATIONS
    # ==========================================
    sales = valid_orders[~cond_unknown_cust & ~cond_unknown_prod].copy()
    sales["gross_amount"] = sales["qty"] * sales["unit_price"]
    sales["discount_amount"] = sales["gross_amount"] * sales["discount_pct"] / 100.0
    sales["sales_amount"] = sales["gross_amount"] - sales["discount_amount"]

    return clean_customers, clean_products, sales, rejects
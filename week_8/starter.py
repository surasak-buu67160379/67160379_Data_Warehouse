# =====================================================================
# Data Integration Pipeline - TechTrove E-Commerce
# การรวมและปรับปรุงข้อมูลให้พร้อมสำหรับการวิเคราะห์ยอดขาย (ETL Process)
# =====================================================================

import pandas as pd
import numpy as np

print("🚀 เริ่มการทำงาน Data Integration Pipeline...")

# =====================================================================
# 1. Extract: นำเข้าข้อมูล (Load Data)
# =====================================================================
print("📥 กำลังโหลดข้อมูลจากโฟลเดอร์ data/ ...")

# โหลดข้อมูล Master Data
df_customers = pd.read_csv('data/customers_crm.csv')
df_products = pd.read_excel('data/product_master.xlsx')
df_payments = pd.read_json('data/payments.json')

# โหลดข้อมูลคำสั่งซื้อ
df_order_m1 = pd.read_csv('data/orders_2026_01.csv')
df_order_m2 = pd.read_csv('data/orders_2026_02.csv')

# รวมข้อมูลคำสั่งซื้อด้วย pd.concat()
df_all_orders = pd.concat([df_order_m1, df_order_m2], ignore_index=True)


# =====================================================================
# 2. สำรวจคุณภาพข้อมูลเบื้องต้น
# =====================================================================
def check_data_quality(df, df_name):
    return {
        'Table': df_name,
        'Total_Rows': len(df),
        'Missing_Values': df.isnull().sum().sum(),
        # เพิ่ม .astype(str) เพื่อแก้ปัญหา unhashable type: 'dict' จากไฟล์ JSON
        'Duplicates': df.astype(str).duplicated().sum() 
    }

# เก็บสถิติก่อนทำความสะอาด
quality_report = []
quality_report.append(check_data_quality(df_customers, 'Customers_Before'))
quality_report.append(check_data_quality(df_products, 'Products_Before'))
quality_report.append(check_data_quality(df_all_orders, 'Orders_Before'))


# =====================================================================
# 3. Transform: ทำความสะอาดและปรับข้อมูลให้เป็นมาตรฐาน (Data Cleaning)
# =====================================================================
print("🧹 กำลังทำความสะอาดข้อมูล (Data Cleaning)...")

# --- คลีนข้อมูลลูกค้า ---
if 'email' in df_customers.columns:
    df_customers['email'] = df_customers['email'].str.lower()

if 'province' in df_customers.columns:
    df_customers['province'] = df_customers['province'].str.strip().str.title()

if 'customer_id' in df_customers.columns:
    df_customers = df_customers.drop_duplicates(subset=['customer_id'])

# --- คลีนข้อมูลสินค้า ---
if 'unit_price' in df_products.columns:
    df_products['unit_price'] = df_products['unit_price'].astype(float)
    
if 'product_id' in df_products.columns:
    df_products = df_products.drop_duplicates(subset=['product_id'])

# --- คลีนข้อมูลคำสั่งซื้อ ---
if 'order_date' in df_all_orders.columns:
    df_all_orders['order_date'] = pd.to_datetime(df_all_orders['order_date'], errors='coerce')

if 'order_id' in df_all_orders.columns and 'product_id' in df_all_orders.columns:
    df_all_orders = df_all_orders.drop_duplicates(subset=['order_id', 'product_id'])


# =====================================================================
# 4. Integration & Modeling: เชื่อมโยงข้อมูลและคำนวณยอดขาย
# =====================================================================
print("🔗 กำลังเชื่อมโยงข้อมูลและคำนวณยอดขายสุทธิ...")

# เชื่อมข้อมูล
df_merged = pd.merge(df_all_orders, df_products, on='product_id', how='left')
df_merged = pd.merge(df_merged, df_customers, on='customer_id', how='left')
df_merged = pd.merge(df_merged, df_payments, on='order_id', how='left')

# จัดการค่าว่างของส่วนลด (ถ้ามีให้เป็น 0)
if 'discount' in df_merged.columns:
    df_merged['discount'] = df_merged['discount'].fillna(0)
else:
    df_merged['discount'] = 0 

# คำนวณยอดขายสุทธิ: net_sales = quantity × unit_price × (1 - discount)
df_merged['net_sales'] = df_merged['quantity'] * df_merged['unit_price'] * (1 - df_merged['discount'])


# =====================================================================
# 5. สร้าง Dimension Table, Fact Table และ Data Quality Report
# =====================================================================
# สร้างตาราง
dim_customer = df_customers.copy()
dim_product = df_products.copy()
fact_sales = df_merged.copy()

# บันทึกสถิติหลังทำความสะอาดและรวมไฟล์
quality_report.append(check_data_quality(df_customers, 'Customers_After'))
quality_report.append(check_data_quality(df_products, 'Products_After'))
quality_report.append(check_data_quality(df_all_orders, 'Orders_After'))
quality_report.append(check_data_quality(df_merged, 'Integrated_Data'))

data_quality_df = pd.DataFrame(quality_report)


# =====================================================================
# 6. วิเคราะห์ผลและส่งออกไฟล์ (Load)
# =====================================================================
print("📊 กำลังวิเคราะห์ผลและสร้างไฟล์ CSV...")
import os

# สร้างโฟลเดอร์ 'output' ถ้าย้งไม่มี
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# สรุปยอดขายแยกตามจังหวัด
if 'province' in df_merged.columns:
    summary_by_province = df_merged.groupby('province')['net_sales'].sum().reset_index()
    summary_by_province = summary_by_province.sort_values(by='net_sales', ascending=False)
else:
    summary_by_province = pd.DataFrame({'Message': ['Column province not found']})

# สรุปยอดขายแยกตามหมวดสินค้า
if 'category' in df_merged.columns:
    summary_by_category = df_merged.groupby('category')['net_sales'].sum().reset_index()
    summary_by_category = summary_by_category.sort_values(by='net_sales', ascending=False)
else:
    summary_by_category = pd.DataFrame({'Message': ['Column category not found']})

# ส่งออกไฟล์ผลลัพธ์ทั้ง 6 ไฟล์ไปที่โฟลเดอร์ output
dim_customer.to_csv(f'{output_dir}/dim_customer.csv', index=False)
dim_product.to_csv(f'{output_dir}/dim_product.csv', index=False)
fact_sales.to_csv(f'{output_dir}/fact_sales.csv', index=False)
data_quality_df.to_csv(f'{output_dir}/data_quality_report.csv', index=False)
summary_by_province.to_csv(f'{output_dir}/summary_by_province.csv', index=False)
summary_by_category.to_csv(f'{output_dir}/summary_by_category.csv', index=False)

print(f"✅ รันโปรแกรมสำเร็จ! สร้างไฟล์ผลลัพธ์ทั้ง 6 ไฟล์เก็บไว้ในโฟลเดอร์ '{output_dir}' เรียบร้อยแล้ว")
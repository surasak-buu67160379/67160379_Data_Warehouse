# ETL Lab Report

Student ID: 67160379
Name: นายสุรศักดิ์ นึกรักษ์

## 1. Data Quality Problems Found
- Duplicate แถวซ้ำ: พบข้อมูลซ้ำตาม Primary Key ใน customers.csv (ซ้ำ 2 รายการ) และ orders.csv (ซ้ำ 3 รายการ)

- Inconsistent Date Formats(formatไม่ตรงกัน): วันที่ (order_date) ใน orders.csv มีหลายรูปแบบปะปนกัน เช่น YYYY/MM/DD, DD/MM/YYYY, YYYY-MM-DD และ DD-Mon-YYYY

- Inconsistent Text Formatting:

        1.ชื่อจังหวัด (province) ใน Customers สะกดหลายแบบทั้งภาษาไทย/อังกฤษ/ตัวย่อ (เช่น bkk, กรุงเทพ, Bangkok, ชลบุรี)

        2.สถานะ (status) ใน Orders มีตัวพิมพ์เล็ก/พิมพ์ใหญ่อ่านไม่สม่ำเสมอ (เช่น PAID, paid, completed)

- Data Formatting & Type Issues: ฟิลด์ราคา (price) ใน products.json มีการใส่เครื่องหมายจุลภาค , (เช่น "1,200.00") และถูกจัดเก็บเป็น String

- Missing Values: พบค่าว่าง (Null / NaN) ในฟิลด์ email และ province ของข้อมูลลูกค้า

- Invalid Record Values (ข้อมูลที่ไม่ปกติ): พบข้อมูลผิดเงื่อนไขทางธุรกิจใน Orders ได้แก่ จำนวนสินค้าติดลบทั้งที่ไม่ควร (qty <= 0), ราคาต่อหน่วยติดลบ (unit_price <= 0), ส่วนลดเกิน 100% (discount_pct > 100), และข้อความวันที่ที่ไม่ถูกต้อง (not-a-date)

## 2. Cleaning / Transformation Rules
- Deduplication: กำจัดแถวซ้ำโดยยึด customer_id และ order_id เป็นหลัก
- Date Standardization: แปลงวันที่ทุกสไตล์ให้อยู่ในรูปแบบมาตรฐานสากล YYYY-MM-DD 
- Text Normalization:
  
            1.ใช้ Province Mapping Dict แปลงชื่อจังหวัดหลากรูปแบบให้เป็นชื่อภาษาอังกฤษมาตรฐาน (เช่น Bangkok, Chonburi, Rayong)
  
            2.ปรับแต่งค่า status ให้เป็นตัวพิมพ์เล็กทั้งหมดและตัด Space ส่วนเกิน
  
- Missing Value Imputation: เติมค่า Default ให้กับข้อมูลที่ขาดหาย (email เติม unknown@example.com, province เติม Unknown)
- Type Casting: ลบเครื่องหมาย , ในราคาของสินค้า แล้วแปลงประเภทข้อมูลเป็น float
- Filtering & Data Validation:
  
            1.แยกข้อมูลที่ผิดกฎธุรกิจเข้าตาราง rejects.csv
  
            2.คัดกรองเอาเฉพาะออเดอร์ที่มีสถานะชำระเงินสำเร็จ (paid และ completed) ไปคำนวณยอดขาย

- Business Calculations:
            1.gross_amount = qty * unit_price
            2.discount_amount = gross_amount * (discount_pct / 100)
            3.sales_amount = gross_amount - discount_amount

## 3. Rejected Records  
จำนวน:4 รายการ

เหตุผลหลัก:

        1.O0007: จำนวนสั่งซื้อติดลบ (qty = -2) -> Invalid Record Rules

        2.O0021: ส่วนลดเกิน 100% (discount_pct = 150) -> Invalid Record Rules

        3.O0034: รูปแบบวันที่ไม่ถูกต้อง (order_date = 'not-a-date') -> Invalid Record Rules

        4.O0091: ราคาต่อหน่วยติดลบ (unit_price = -100.0) -> Invalid Record Rules

## 4. ETL Validation
- Valid transformed rows: 100 รายการ
- Warehouse rows: 100 รายการ
- Duplicate order_id: 0 รายการ
- Source total sales: 192,074.66 บาท
- Warehouse total sales: 192,074.66 บาท
- Validation status: จำนวนแถวและยอดขายรวมใน Warehouse ตรงกับ ข้อมูลที่ผ่านการ Transformแล้ว 

## 5. Idempotency Test
จำนวน fact_sales หลัง run ครั้งที่ 1: 100 รายการ

จำนวน fact_sales หลัง run ครั้งที่ 2: 100 รายการ

อธิบายผล:
ระบบ ETL มีคุณสมบัติ Idempotency เนื่องจากเมื่อทำการสั่งรัน Pipeline ซ้ำเป็นครั้งที่ 2 ด้วยข้อมูลชุดเดิม ระบบทำการเขียนทับ/อัปเดตข้อมูลเดิมได้อย่างถูกต้อง (เช่น การใช้ if_exists='replace' หรือ UPSERT) ส่งผลให้จำนวนแถวในตาราง fact_sales ยังคงเป็น 100 รายการ และยอดขายรวมคงที่ที่ 192,074.66 บาท เท่าเดิม ไม่เกิดการสร้างข้อมูลซ้ำซ้อนหรือทำให้ยอดขายเพิ่มขึ้นผิดปกติ

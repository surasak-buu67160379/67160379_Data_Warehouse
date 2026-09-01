โครงสร้างโปรเจกต์ (Project Structure)
week8/
├── config.py             # ตั้งค่าระบบ, Path ของไฟล์, และ Logging
├── extract.py            # ดึงข้อมูลจากไฟล์ Excel (ใช้ Polars)
├── transform.py          # ทำความสะอาดข้อมูล, กรองของเสีย, คำนวณยอดเงิน
├── load.py               # จัดการ DDL สร้างตาราง และโหลดข้อมูลลง SQLite
├── main.py               # ไฟล์หลักสำหรับรันและควบคุมการทำงานของ Pipeline
├── data/
│   └── Python_Data_Pipeline_Lab_Dataset.xlsx  # ไฟล์ข้อมูลต้นทาง
└── output/               # (ระบบสร้างให้อัตโนมัติเมื่อรัน)
    ├── retail_dw.db          # ฐานข้อมูล SQLite (Star Schema)
    ├── quarantine.csv        # รายการข้อมูลที่ไม่ผ่านเกณฑ์ พร้อมระบุสาเหตุ
    └── pipeline_run_log.csv  # ประวัติการทำงานของ Pipeline ในแต่ละ Batch


วิธีติดตั้ง (Setup)
1. ต้องมีไฟล์ Python_Data_Pipeline_Lab_Dataset.xlsx วางอยู่ในโฟลเดอร์ data/
2. ติดตั้ง Library ที่จำเป็น (Polars และตัวอ่าน Excel):

    pip install polars openpyxl

วิธีรันโปรแกรม (How to Run)
รันคำสั่งด้านล่างที่โฟลเดอร์รันโปรเจกต์:

    python main.py

ระบบจะทำการจำลองรันข้อมูล 4 รอบตามลำดับ เพื่อสาธิตการทำงานแบบ Idempotency (รันซ้ำข้อมูลไม่เบิ้ล) และ Incremental Loading (ดึงเฉพาะข้อมูลใหม่):
รอบที่ 1: โหลด orders_batch_1 (จำลองการโหลดข้อมูลครั้งแรก)
รอบที่ 2: โหลด orders_batch_1 ซ้ำ (ตรวจสอบว่า Fact Table ไม่บันทึกข้อมูลซ้ำ)
รอบที่ 3: โหลด orders_batch_2 (อัปเดตข้อมูลชุดใหม่)
รอบที่ 4: โหลด orders_batch_3 (อัปเดตข้อมูลชุดใหม่)

โครงสร้างฐานข้อมูล (Star Schema)
ข้อมูลที่ผ่านการคัดกรองจะถูกจัดเก็บลงในไฟล์ output/retail_dw.db ซึ่งประกอบด้วยตารางดังนี้:
dim_customer	เก็บข้อมูลลูกค้า (1 แถว / 1 ลูกค้า)
dim_product	เก็บข้อมูลสินค้า (1 แถว / 1 สินค้า)
dim_date	เก็บข้อมูลมิติเวลา (สร้างอัตโนมัติจากวันที่สั่งซื้อ)
fact_sales	ตารางหลักเก็บยอดขาย (1 แถว / 1 ออเดอร์ ที่ผ่านการตรวจสอบ)
quarantine	ถังขยะกักกันข้อมูลที่ไม่ผ่านเกณฑ์ (เช่น Type ผิด, ติดลบ, FK ไม่มีอยู่จริง)
pipeline_run_log      บันทึกประวัติและสถิติการรันแต่ละ Batch




# ระบบรวบรวมข้อมูลความหนาแน่นการจราจรกรุงเทพฯ

งานสอบปฏิบัติรายวิชา 02739452 แพลตฟอร์มข้อมูลขนาดใหญ่และการวิเคราะห์

**หัวข้อ:** ความหนาแน่นการจราจรทางถนนในกรุงเทพฯ
**ขอบเขต:** ระดับรถติดของกรุงเทพฯ ตามช่วงเวลา และเหตุการณ์/ปัญหาบนถนนที่กระทบการจราจรในพื้นที่กรุงเทพมหานคร

ระบบดึงข้อมูลจาก 3 แหล่ง รวมเป็นชุดข้อมูลเดียวด้วย Apache Airflow DAG (รันทุก 15 นาที) เก็บใน PostgreSQL และแสดงผลบนเว็บ dashboard (Streamlit) ที่อ่านจาก PostgreSQL โดยตรง

> **ไม่ต้องใช้ API key** ทุกแหล่งเปิดให้เข้าถึงแบบสาธารณะ clone แล้วรันได้ทันที

## แหล่งข้อมูล

| # | แหล่ง | วิธีดึง | ข้อมูลที่ได้ | robots.txt |
|---|---|---|---|---|
| 1 | [TomTom Traffic Index – Bangkok](https://www.tomtom.com/traffic-index/bangkok-traffic/) | **Web scraping** ด้วย `requests` (ไม่ใช้ Selenium) อ่านข้อมูลที่ฝังอยู่ใน HTML ของหน้าเว็บ | ระดับรถติด (%) ความเร็ว และความเร็วตอนถนนโล่งของกรุงเทพฯ: รายชั่วโมงทั้งสัปดาห์ (168 ค่า), รายเดือน (12 ค่า), ช่วงเร่งด่วนเช้า/เย็น | อนุญาต (`User-agent: *` ห้ามแค่ `*/account/`) |
| 2 | [Longdo Traffic event feed](https://event.longdo.com/feed/json) | JSON feed | เหตุการณ์จราจรล่าสุด เช่น น้ำท่วม อุบัติเหตุ ก่อสร้าง พร้อมพิกัด (กรองเฉพาะกรุงเทพฯ) | อนุญาต โดยขอ `Crawl-delay: 10` ซึ่งโค้ดทำตาม |
| 3 | [Traffy Fondue](https://publicapi.traffy.in.th/share/teamchadchart/search) | Public API (JSON) | เรื่องร้องเรียนของ กทม. เลือกเฉพาะหมวดถนน จราจร น้ำท่วม สะพาน ทางเท้า | ไม่มี robots.txt (404) |

**ชุดข้อมูลรวม:** ทุกแหล่งถูกแปลงเป็น schema เดียวกันในตาราง `traffic_record`
`source, source_id, record_type, category, title, area, period, event_time, lat, lon, congestion_pct, speed_kmh, free_flow_kmh, severity, dedup_key`
- `record_type = congestion` (TomTom), `incident` (Longdo), `complaint` (Traffy)

**การปฏิบัติตามข้อกำหนด**
- ก่อนดึงทุกครั้ง โค้ดจะอ่าน `robots.txt` ด้วย `urllib.robotparser` ถ้าไม่อนุญาตจะไม่ดึง และถ้ามี `Crawl-delay` จะรอตามที่กำหนด (ดู `check_robots()` ใน `dags/traffic/sources.py`)
- PDPA: **ไม่เก็บ** ชื่อผู้รายงาน (`contributor` ของ Longdo), ข้อความร้องเรียน (`description`) และรูปภาพของ Traffy เพราะอาจมีข้อมูลส่วนบุคคล เก็บเฉพาะประเภท พิกัด เวลา เขต และสถานะ
- ไม่มีรหัสผ่านหรือ key ใน repo มีแค่ `.env.example`

## สถาปัตยกรรม

```
              ┌─ extract.tomtom_index (scrape) ─┐
TaskGroup ────┼─ extract.longdo       (feed)   ─┼──> transform ──> quality_check ──┬─> load.upsert_records ─> load.dedupe_events ─┐
(รันขนาน)      └─ extract.traffy       (API)    ─┘   (all_done)     (branch)        └─> quarantine ─────────────────────────────────┴─> record_run
```

| Task | หน้าที่ |
|---|---|
| `extract.*` | ดึงข้อมูลแต่ละแหล่งขนานกันใน TaskGroup ถ้าเว็บล่มจะเป็น **failed**, ถ้าปิดแหล่งใน `.env` จะเป็น **skipped** |
| `transform` | `trigger_rule="all_done"` จึงทำงานต่อแม้บางแหล่งล่ม แปลงทุกแหล่งเป็น schema เดียว กรองเฉพาะพื้นที่กรุงเทพฯ ตรวจกฎรายแถว และตัดรายการซ้ำภายในรอบ |
| `quality_check` | `@task.branch` ถ้าแถวที่ใช้ได้ ≥ 10 และแถวเสีย ≤ 30% ไป `load` ไม่อย่างนั้นไป `quarantine` |
| `load.upsert_records` | `INSERT ... ON CONFLICT (source, source_id) DO UPDATE` ทำให้ **รันซ้ำแล้วจำนวนแถวไม่เพิ่ม** (log จะพิมพ์จำนวนแถวก่อน/หลัง) |
| `load.dedupe_events` | **ตัดรายการซ้ำข้ามแหล่ง** โดยเหตุการณ์จาก Longdo และ Traffy ที่อยู่ในกลุ่มเดียวกัน (น้ำท่วม / ถนนและจราจร) วันเดียวกัน และอยู่ในช่องกริดเดียวกัน (~300 ม.) จะรวมเหลือ 1 แถวในตาราง `traffic_event` |
| `quarantine` | ไม่นำข้อมูลรอบนั้นเข้าตารางหลัก |
| `record_run` | บันทึกสถานะรอบ (SUCCESS / PARTIAL / QUALITY_FAILED) และแถวที่ไม่ผ่านลง `pipeline_run`, `quality_issue` |

**กฎตรวจคุณภาพรายแถว:** ฟิลด์ที่จำเป็นต้องไม่ว่าง (แยกตามประเภท), ระดับรถติด 0–300%, ความเร็ว 0–150 กม./ชม., ความรุนแรง 0–5, พิกัดต้องอยู่ในกรุงเทพฯ และเวลาต้องไม่อยู่ในอนาคต

**ตารางใน PostgreSQL (ฐานข้อมูล `traffic`)**: `traffic_record` (ข้อมูลรวม), `traffic_event` (ตัดซ้ำข้ามแหล่งแล้ว), `quality_issue`, `pipeline_run` (ดู `sql/schema.sql`)

## งานที่ทำได้ตามระดับ

| ระดับ | สิ่งที่ทำ |
|---|---|
| 1 | DAG extract → transform → load → PostgreSQL → เว็บมีตารางและกราฟ |
| 2 | 3 แหล่งรันขนานใน TaskGroup, schema เดียวกัน, UPSERT (รันซ้ำแถวไม่เพิ่ม), เว็บมี KPI และตัวกรอง (แหล่ง, ช่วงวัน, ประเภท, คำค้น) |
| 3 | แหล่งล่มแล้วยังรวมจากแหล่งที่เหลือ (`all_done`), ตัดรายการซ้ำข้ามแหล่ง (`traffic_event`), ตรวจคุณภาพแล้วแตกเส้นทาง (`@task.branch` → `quarantine`) |
| โบนัส | หน้า **Pipeline Status** บนเว็บ: สถานะแต่ละแหล่ง ประวัติการรัน และปัญหาคุณภาพข้อมูล |

ข้อมูลต่อรอบ: TomTom ประมาณ 184 แถว + Longdo (เฉพาะกรุงเทพฯ) + Traffy (เรื่องด้านถนน/จราจรจาก 500 เรื่องล่าสุด) **รอบแรกก็เกิน 100 รายการ**

## วิธีรัน

ต้องมี Docker Desktop (หรือ Docker Engine + Compose v2)

```bash
git clone https://github.com/Bannawat1/02739452-24-6621655274.git
cd 02739452-24-6621655274
cp .env.example .env          # Windows: copy .env.example .env
docker compose up -d --build  # ครั้งแรกใช้เวลา 5-10 นาที
```

| บริการ | URL | หมายเหตุ |
|---|---|---|
| Airflow | http://localhost:8080 | user/pass ตาม `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` ใน `.env` |
| Web dashboard | http://localhost:8501 | มี 2 หน้า: dashboard และ Pipeline Status |
| PostgreSQL | localhost:5432 | db `traffic` user/pass ตาม `TRAFFIC_DB_USER` / `TRAFFIC_DB_PASSWORD` ใน `.env` |

DAG `bkk_traffic_pipeline` เปิดใช้อัตโนมัติและรันทุก 15 นาที ถ้าอยากเห็นผลทันทีให้กดปุ่ม ▶ (Trigger DAG) ในหน้า Airflow รอประมาณ 1 นาที แล้วรีเฟรชหน้าเว็บ

### ทดสอบ
```bash
pip install -r requirements.txt
pytest tests          # ทดสอบการ scrape/parse, การกรอง PDPA, dedup ข้ามแหล่ง, robots.txt และกฎคุณภาพ
```

### ทดสอบ UPSERT (รันซ้ำแล้วแถวไม่เพิ่ม)
ใน Airflow เลือกรอบที่รันแล้ว > กด **Clear** > รอรันเสร็จ แล้วดู log ของ `load.upsert_records` จะขึ้นว่า `ตารางมี N -> N แถว (ใหม่ 0)` หรือเช็กด้วยคำสั่ง:
```bash
docker compose exec postgres psql -U traffic -d traffic -c "SELECT source, COUNT(*) FROM traffic_record GROUP BY source"
```

### ทดสอบกรณีแหล่งล่ม / ข้อมูลไม่ผ่าน
- ตั้ง `ENABLE_TRAFFY=false` ใน `.env` แล้วสั่ง `docker compose up -d` แหล่งนั้นจะเป็น skipped แต่ DAG ยังรวมสองแหล่งที่เหลือต่อ (สถานะ PARTIAL)
- ตั้ง `DQ_MIN_VALID_ROWS=100000` แล้วสั่ง `docker compose up -d` รอบถัดไปจะไปทาง `quarantine`

## โครงสร้างไฟล์

```
├── dags/
│   ├── bkk_traffic_dag.py        # DAG หลัก
│   └── traffic/
│       ├── sources.py            # extract/parse ของ TomTom, Longdo, Traffy + ตรวจ robots.txt
│       └── quality.py            # transform + กฎคุณภาพข้อมูล
├── web/
│   ├── app.py                    # Dashboard หลัก
│   ├── pages/1_Pipeline_Status.py  # หน้าสถานะ pipeline (โบนัส)
│   ├── db.py, theme.py
│   └── Dockerfile
├── sql/init.sh, sql/schema.sql   # สร้างฐานข้อมูล (อ่านรหัสผ่านจาก .env) และตาราง
├── tests/                        # unit tests (ใช้ตัวอย่างข้อมูลจริงของแต่ละแหล่ง)
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## แก้ปัญหาเบื้องต้น
- **`extract.tomtom_index` failed ด้วย "ไม่พบข้อมูล traffic ในหน้าเว็บ"**: โครงสร้างหน้าเว็บของ TomTom เปลี่ยน DAG ยังรวมข้อมูลจาก Longdo และ Traffy ต่อได้
- **Linux แล้ว logs เขียนไม่ได้**: ใส่ `AIRFLOW_UID=$(id -u)` ใน `.env`
- **พอร์ตชน**: แก้พอร์ตฝั่งซ้ายใน `docker-compose.yml` เช่น `"5433:5432"`

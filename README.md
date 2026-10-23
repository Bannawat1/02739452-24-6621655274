# ระบบรวบรวมข้อมูลความหนาแน่นการจราจรกรุงเทพฯ

งานสอบปฏิบัติรายวิชา 02739452 แพลตฟอร์มข้อมูลขนาดใหญ่และการวิเคราะห์

**หัวข้อ:** ความหนาแน่นการจราจรทางถนนในกรุงเทพฯ แบบใกล้เรียลไทม์ (ทุก 15 นาที)
**ขอบเขต:** ถนนสายหลักในพื้นที่กรุงเทพมหานคร

ระบบดึงข้อมูลจาก 3 แหล่ง รวมเป็นชุดข้อมูลเดียวด้วย Apache Airflow DAG เก็บใน PostgreSQL และแสดงผลบนเว็บ dashboard (Streamlit) ที่อ่านจาก PostgreSQL โดยตรง

## แหล่งข้อมูล

| # | แหล่ง | วิธีดึง | ข้อมูลที่ได้ | ต้องใช้ key |
|---|---|---|---|---|
| 1 | [Waze Live Map](https://www.waze.com/live-map) | **Web scraping** ด้วย `requests` (ไม่ใช้ Selenium) อ่านข้อมูลรถติดที่หน้า Live Map โหลดมาแสดง | รายการรถติดแต่ละช่วงถนน: ชื่อถนน, ระดับ 0–5, ความเร็ว, ความยาว, ความล่าช้า | ไม่ต้อง |
| 2 | [TomTom Routing API](https://developer.tomtom.com/routing-api/documentation) | REST API | เวลาเดินทางจริงเทียบกับตอนถนนโล่ง ของ 15 ช่วงถนนหลัก | `TOMTOM_API_KEY` (ฟรี) |
| 3 | [HERE Routing API v8](https://www.here.com/docs/bundle/routing-api-developer-guide-v8/page/README.html) | REST API | เวลาเดินทางจริง (`duration`) เทียบกับ `baseDuration` ของ 15 ช่วงถนนเดียวกัน | `HERE_API_KEY` (ฟรี) |

ทุกแหล่งถูกแปลงเป็น schema เดียวกัน: `source, source_id, observed_at, road, road_key, length_m, speed_kmh, delay_s, jam_level (0–5), lat, lon`
TomTom และ HERE ใช้ **Travel Time Index (TTI)** = เวลาจริง ÷ เวลาตอนถนนโล่ง แล้วแปลงเป็นระดับ 0–5 แบบเดียวกับ Waze

**การปฏิบัติตามข้อกำหนด**
- ก่อน scrape ทุกครั้ง โค้ดจะอ่าน `robots.txt` ด้วย `urllib.robotparser` ถ้าไม่อนุญาตจะไม่ดึง (ดู `check_robots()` ใน `dags/traffic/sources.py`)
- PDPA: เก็บเฉพาะข้อมูลถนนและการจราจร ไม่เก็บข้อมูลผู้ใช้หรือผู้รายงาน (ดึงเฉพาะ `types=traffic` ไม่ดึง alerts ที่มีชื่อผู้รายงาน)
- ไม่มี API key ใน repo ใช้ `.env.example` เป็นแม่แบบ

## สถาปัตยกรรม

```
              ┌─ extract.waze   (scrape) ─┐
TaskGroup ────┼─ extract.tomtom (API)    ─┼──> transform ──> quality_check ──┬─> load.upsert_records ─> load.dedupe_road_status ─┐
(รันขนาน)      └─ extract.here   (API)    ─┘   (all_done)     (branch)        └─> quarantine ───────────────────────────────────┴─> record_run
```

| Task | หน้าที่ |
|---|---|
| `extract.*` | ดึงข้อมูลแต่ละแหล่งขนานกันใน TaskGroup ถ้าไม่มี key จะเป็น **skipped**, ถ้าเว็บ/API ล่มจะเป็น **failed** |
| `transform` | `trigger_rule="all_done"` จึงทำงานต่อแม้บางแหล่งล่ม แปลงทุกแหล่งเป็น schema เดียว ตรวจกฎรายแถว และตัดรายการซ้ำภายในรอบ |
| `quality_check` | `@task.branch` ถ้าแถวที่ใช้ได้ ≥ 10 และแถวเสีย ≤ 30% ไป `load` ไม่อย่างนั้นไป `quarantine` |
| `load.upsert_records` | `INSERT ... ON CONFLICT (source, source_id, observed_at) DO UPDATE` และลบแถวเก่าของรอบเดียวกันที่ไม่อยู่ในชุดใหม่ ทำให้ **รันซ้ำแล้วจำนวนแถวไม่เพิ่ม** |
| `load.dedupe_road_status` | **ตัดรายการซ้ำข้ามแหล่ง** โดยรวมถนนเดียวกัน (จับคู่ด้วย `road_key` เช่น `ถ.พระราม 4` = `Rama IV Rd`) ให้เหลือ 1 แถวต่อถนนต่อรอบ |
| `quarantine` | ไม่นำข้อมูลรอบนั้นเข้าตารางหลัก |
| `record_run` | บันทึกสถานะรอบ (SUCCESS / PARTIAL / QUALITY_FAILED) และแถวที่ไม่ผ่านลง `pipeline_run`, `quality_issue` |

**ตารางใน PostgreSQL (ฐานข้อมูล `traffic`)**: `traffic_record` (ข้อมูลรวมทุกแหล่ง), `road_status` (ตัดซ้ำข้ามแหล่งแล้ว), `quality_issue`, `pipeline_run` (ดู `sql/init.sql`)

## งานที่ทำได้ตามระดับ

| ระดับ | สิ่งที่ทำ |
|---|---|
| 1 | DAG extract → transform → load → PostgreSQL → เว็บมีตารางและกราฟ |
| 2 | 3 แหล่งรันขนานใน TaskGroup, schema เดียวกัน, UPSERT (รันซ้ำแถวไม่เพิ่ม), เว็บมี KPI และตัวกรอง (รอบเวลา, แหล่ง, ระดับ, ชื่อถนน) |
| 3 | แหล่งล่มแล้วยังรวมจากแหล่งที่เหลือ (`all_done`), ตัดรายการซ้ำข้ามแหล่ง (`road_status`), ตรวจคุณภาพแล้วแตกเส้นทาง (`@task.branch` → `quarantine`) |
| โบนัส | หน้า **สถานะ Pipeline** บนเว็บ: สถานะแต่ละแหล่ง ประวัติการรัน และปัญหาคุณภาพข้อมูล |

## วิธีรัน

ต้องมี Docker Desktop (หรือ Docker Engine + Compose v2)

```bash
git clone <URL ของ repo นี้>
cd <โฟลเดอร์ repo>
cp .env.example .env          # ใส่ TOMTOM_API_KEY / HERE_API_KEY (ถ้าไม่ใส่ ระบบยังได้ข้อมูลจาก Waze)
docker compose up -d --build  # ครั้งแรกใช้เวลา 3-5 นาที
```

| บริการ | URL | หมายเหตุ |
|---|---|---|
| Airflow | http://localhost:8080 | user `admin` / pass `admin` |
| Web dashboard | http://localhost:8501 | มี 2 หน้า: dashboard และสถานะ Pipeline |
| PostgreSQL | localhost:5432 | db `traffic` user `traffic` pass `traffic` |

DAG `bkk_traffic_pipeline` เปิดใช้อัตโนมัติและรันทุก 15 นาที ถ้าอยากเห็นผลทันทีให้กดปุ่ม ▶ (Trigger DAG) ในหน้า Airflow

ข้อมูลแต่ละรอบ: Waze ราว 100–300 รายการ + TomTom 15 + HERE 15 ดังนั้นรอบแรกก็เกิน 100 รายการแล้ว

### ขอ API key (ฟรี)
- **TomTom**: สมัครที่ https://developer.tomtom.com แล้ว key จะอยู่ใน Dashboard > Keys (ไม่ต้องผูกบัตร)
- **HERE**: สมัครที่ https://platform.here.com แล้วไปที่ Access Manager > Apps > สร้าง app > API Keys

แก้ `.env` แล้วรัน `docker compose up -d` อีกครั้งเพื่อให้ Airflow อ่าน key ใหม่

### ทดสอบ
```bash
pip install -r requirements.txt
pytest tests          # ทดสอบ parse / transform / robots.txt / กฎคุณภาพ ด้วยตัวอย่าง response
```

### ทดสอบ UPSERT (รันซ้ำแล้วแถวไม่เพิ่ม)
ใน Airflow เลือกรอบที่รันแล้ว > กด **Clear** > รอรันเสร็จ จากนั้นเช็กว่าจำนวนแถวไม่เพิ่ม:
```bash
docker compose exec postgres psql -U traffic -d traffic -c "SELECT observed_at, COUNT(*) FROM traffic_record GROUP BY 1 ORDER BY 1 DESC LIMIT 5"
```

### ทดสอบกรณีแหล่งล่ม / ข้อมูลไม่ผ่าน
- ลบ `TOMTOM_API_KEY` ออก แหล่งนี้จะ skipped แต่ DAG ยังรวม Waze และ HERE ต่อ (สถานะ PARTIAL)
- ตั้ง `DQ_MIN_VALID_ROWS=100000` ใน `.env` แล้ว `docker compose up -d` รอบถัดไปจะไปทาง `quarantine`

## โครงสร้างไฟล์

```
├── dags/
│   ├── bkk_traffic_dag.py      # DAG หลัก
│   └── traffic/
│       ├── corridors.py        # ช่วงถนน + normalize ชื่อถนน (road_key)
│       ├── sources.py          # extract/parse ของ Waze, TomTom, HERE + ตรวจ robots.txt
│       └── quality.py          # transform + กฎคุณภาพข้อมูล
├── web/
│   ├── app.py                  # Dashboard หลัก
│   ├── pages/1_Pipeline_Status.py  # หน้าสถานะ pipeline (โบนัส)
│   ├── db.py
│   └── Dockerfile
├── sql/init.sql                # สร้างฐานข้อมูลและตาราง
├── tests/                      # unit tests
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## แก้ปัญหาเบื้องต้น
- **`extract.waze` failed**: ดู log ใน Airflow ถ้าเป็น `robots.txt ไม่อนุญาต` แปลว่าระบบหยุด scrape ตามข้อกำหนด ถ้าเป็น HTTP 403 แปลว่าเว็บปฏิเสธ request DAG ยังรวมข้อมูลจากแหล่งที่เหลือต่อ
- **Linux แล้ว logs เขียนไม่ได้**: ใส่ `AIRFLOW_UID=$(id -u)` ใน `.env`
- **พอร์ตชน**: แก้พอร์ตฝั่งซ้ายใน `docker-compose.yml` เช่น `"5433:5432"`

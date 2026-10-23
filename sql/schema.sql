-- ตารางของฐานข้อมูล traffic (สร้างโดย sql/init.sh ตอนเริ่ม container ครั้งแรก)

-- ชุดข้อมูลรวม: ทุกแหล่งอยู่ใน schema เดียวกัน
--   record_type = congestion (TomTom: % รถติด) / incident (Longdo: เหตุการณ์) / complaint (Traffy: เรื่องร้องเรียน)
CREATE TABLE traffic_record (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,              -- tomtom_index / longdo / traffy
    source_id       TEXT NOT NULL,              -- รหัสของรายการในแหล่งนั้น
    record_type     TEXT NOT NULL,
    category        TEXT NOT NULL,              -- เช่น weekHour, monthly, flood, accident, road, traffic
    title           TEXT,
    area            TEXT,
    period          TEXT,                       -- ช่วงเวลาของค่าสถิติ เช่น "1-Monday 08:00", "2025-03"
    event_time      TIMESTAMPTZ,                -- เวลาที่เกิดเหตุการณ์/แจ้งเรื่อง
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    congestion_pct  NUMERIC(6,2),               -- % เวลาเดินทางที่เพิ่มขึ้นจากตอนถนนโล่ง
    speed_kmh       NUMERIC(6,2),
    free_flow_kmh   NUMERIC(6,2),
    severity        SMALLINT,
    dedup_key       TEXT,                       -- ใช้จับคู่เหตุการณ์เดียวกันข้ามแหล่ง
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id)                  -- ใช้ทำ UPSERT: รันซ้ำแล้วจำนวนแถวไม่เพิ่ม
);
CREATE INDEX ON traffic_record (record_type);
CREATE INDEX ON traffic_record (event_time);
CREATE INDEX ON traffic_record (dedup_key);

-- ตัดรายการซ้ำข้ามแหล่ง: เหตุการณ์กลุ่มเดียวกัน วันเดียวกัน ห่างกันไม่เกิน ~300 ม. = 1 แถว
CREATE TABLE traffic_event (
    dedup_key     TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL,
    sources       TEXT[] NOT NULL,
    n_sources     SMALLINT NOT NULL,
    n_records     INT NOT NULL,
    first_time    TIMESTAMPTZ NOT NULL,
    max_severity  SMALLINT,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- แถวที่ไม่ผ่านการตรวจคุณภาพ
CREATE TABLE quality_issue (
    id           BIGSERIAL PRIMARY KEY,
    run_id       TEXT NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    source       TEXT NOT NULL,
    source_id    TEXT,
    problem      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- สถานะของแต่ละรอบ pipeline (ใช้ในหน้าสถานะบนเว็บ)
CREATE TABLE pipeline_run (
    run_id          TEXT PRIMARY KEY,
    observed_at     TIMESTAMPTZ NOT NULL,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_status   JSONB NOT NULL,         -- {"longdo": {"state": "success", "rows": 12}, ...}
    n_raw           INT NOT NULL,
    n_valid         INT NOT NULL,
    n_rejected      INT NOT NULL,
    quality_passed  BOOLEAN NOT NULL,
    quality_reason  TEXT,
    branch          TEXT NOT NULL,          -- load / quarantine
    status          TEXT NOT NULL           -- SUCCESS / PARTIAL / QUALITY_FAILED
);


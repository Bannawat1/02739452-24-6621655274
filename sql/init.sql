-- รันอัตโนมัติครั้งแรกที่สร้าง container postgres
CREATE USER traffic WITH PASSWORD 'traffic';
CREATE DATABASE traffic OWNER traffic;

\connect traffic
SET ROLE traffic;

-- ชุดข้อมูลรวม: ทุกแหล่งอยู่ใน schema เดียวกัน (1 แถว = 1 ช่วงถนน จาก 1 แหล่ง ใน 1 รอบ)
CREATE TABLE traffic_record (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,             -- waze / tomtom / here
    source_id    TEXT NOT NULL,             -- uuid ของ Waze หรือ corridor id
    observed_at  TIMESTAMPTZ NOT NULL,      -- เวลาของรอบ DAG (ปัดลงทุก 15 นาที)
    road         TEXT NOT NULL,
    road_key     TEXT NOT NULL,             -- ชื่อถนนที่ normalize แล้ว ใช้จับคู่ข้ามแหล่ง
    length_m     INT NOT NULL,
    speed_kmh    NUMERIC(6,2) NOT NULL,
    delay_s      INT,
    jam_level    SMALLINT NOT NULL,         -- 0 โล่ง ... 4 ติดหนัก, 5 ถนนปิด
    lat          DOUBLE PRECISION,
    lon          DOUBLE PRECISION,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id, observed_at) -- ใช้ทำ UPSERT: รันซ้ำแล้วจำนวนแถวไม่เพิ่ม
);
CREATE INDEX ON traffic_record (observed_at);
CREATE INDEX ON traffic_record (road_key);

-- ตัดรายการซ้ำข้ามแหล่ง: 1 แถว = 1 ถนน ต่อ 1 รอบ ไม่ว่าจะมีกี่แหล่ง/กี่ช่วงรายงานมา
CREATE TABLE road_status (
    road_key        TEXT NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL,
    road            TEXT NOT NULL,
    sources         TEXT[] NOT NULL,
    n_sources       SMALLINT NOT NULL,
    n_records       INT NOT NULL,
    avg_speed_kmh   NUMERIC(6,2) NOT NULL,
    max_jam_level   SMALLINT NOT NULL,
    total_delay_s   INT,
    total_length_m  INT NOT NULL,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    PRIMARY KEY (road_key, observed_at)
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
    source_status   JSONB NOT NULL,         -- {"waze": {"state": "success", "rows": 312}, ...}
    n_raw           INT NOT NULL,
    n_valid         INT NOT NULL,
    n_rejected      INT NOT NULL,
    quality_passed  BOOLEAN NOT NULL,
    quality_reason  TEXT,
    branch          TEXT NOT NULL,          -- load / quarantine
    status          TEXT NOT NULL           -- SUCCESS / PARTIAL / QUALITY_FAILED
);

RESET ROLE;

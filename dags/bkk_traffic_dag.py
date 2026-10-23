"""ความหนาแน่นการจราจรกรุงเทพฯ: TomTom Traffic Index (scrape) + Longdo + Traffy Fondue -> PostgreSQL

    extract (TaskGroup, รันขนาน)                     transform      quality_check (branch)
    ├─ tomtom_index ─┐
    ├─ longdo       ─┼──> transform ──> quality_check ─┬─> load.upsert_records ─> load.dedupe_events ─┐
    └─ traffy       ─┘   (all_done)                    └─> quarantine ────────────────────────────────┴─> record_run

- ทุกแหล่งไม่ต้องใช้ API key
- แหล่งใดล่ม (failed) transform ยังรวมข้อมูลจากแหล่งที่เหลือต่อ
- UPSERT ด้วย UNIQUE (source, source_id) -> Clear/รันซ้ำแล้วจำนวนแถวไม่เพิ่ม
- dedupe_events รวมเหตุการณ์เดียวกันจาก Longdo และ Traffy (วันเดียวกัน, ห่างกัน ~300 ม., กลุ่มเดียวกัน) ให้เหลือ 1 แถว
"""
from datetime import datetime, timedelta, timezone

import pendulum
from airflow.decorators import dag, task, task_group
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import get_current_context
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import Json, execute_values

from traffic import quality
from traffic.sources import SOURCES, SourceSkipped

CONN_ID = "traffic_db"


def _observed_at():
    """เวลาของรอบ ปัดลงทุก 15 นาที: ทุกแหล่งในรอบเดียวกันใช้ค่าเดียวกัน และรันซ้ำได้ค่าเดิม"""
    ts = get_current_context()["data_interval_end"].in_timezone("Asia/Bangkok")
    return ts.replace(minute=ts.minute - ts.minute % 15, second=0, microsecond=0).isoformat()


@dag(
    dag_id="bkk_traffic_pipeline",
    schedule="*/15 * * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Bangkok"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["traffic", "bangkok"],
    doc_md=__doc__,
)
def bkk_traffic_pipeline():

    @task_group(group_id="extract")
    def extract_group():
        outputs = {}
        for name in SOURCES:
            @task(task_id=name)
            def extract(source=name):
                try:
                    return SOURCES[source]["extract"]()
                except SourceSkipped as e:
                    raise AirflowSkipException(str(e))
            outputs[name] = extract()
        return outputs

    @task(trigger_rule="all_done")
    def transform(raw_by_source):
        ctx = get_current_context()
        # สถานะของแต่ละแหล่ง (success / failed / skipped) เก็บไว้แสดงในหน้าสถานะ
        status = {}
        for name in SOURCES:
            ti = ctx["dag_run"].get_task_instance(f"extract.{name}")
            state = getattr(ti.state, "value", ti.state) or "none"
            status[name] = {"state": state, "kind": SOURCES[name]["kind"],
                            "raw": len(raw_by_source.get(name) or [])}
        if not any(s["state"] == "success" for s in status.values()):
            print("ไม่มีแหล่งไหนดึงสำเร็จเลย")

        records, rejected = quality.transform(raw_by_source)
        for r in records:
            status[r["source"]]["rows"] = status[r["source"]].get("rows", 0) + 1
        print("สถานะแหล่งข้อมูล:", status)
        return {
            "observed_at": _observed_at(),
            "records": records,
            "rejected": rejected,
            "source_status": status,
            "n_raw": sum(s["raw"] for s in status.values()),
        }

    @task.branch
    def quality_check(data):
        passed, reason = quality.evaluate(len(data["records"]), len(data["rejected"]))
        get_current_context()["ti"].xcom_push(key="quality", value={"passed": passed, "reason": reason})
        print(reason)
        return "load.upsert_records" if passed else "quarantine"

    @task_group(group_id="load")
    def load_group(data):

        @task
        def upsert_records(data):
            cols = ("source", "source_id", "record_type", "category", "title", "area", "period", "event_time",
                    "lat", "lon", "congestion_pct", "speed_kmh", "free_flow_kmh", "severity", "dedup_key")
            rows = [tuple(r[c] for c in cols) for r in data["records"]]
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols[2:])
            hook = PostgresHook(postgres_conn_id=CONN_ID)
            with hook.get_conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM traffic_record")
                before = cur.fetchone()[0]
                execute_values(cur, f"""
                    INSERT INTO traffic_record ({", ".join(cols)}) VALUES %s
                    ON CONFLICT (source, source_id) DO UPDATE SET {updates}, last_seen = NOW()
                """, rows)
                cur.execute("SELECT COUNT(*) FROM traffic_record")
                after = cur.fetchone()[0]
            print(f"upsert {len(rows)} แถว: ตารางมี {before} -> {after} แถว (ใหม่ {after - before})")

        @task
        def dedupe_events():
            hook = PostgresHook(postgres_conn_id=CONN_ID)
            with hook.get_conn() as conn, conn.cursor() as cur:
                # สร้างตารางเหตุการณ์ที่ตัดซ้ำข้ามแหล่งแล้วใหม่ทั้งหมด จากเหตุการณ์ 30 วันล่าสุด
                cur.execute("DELETE FROM traffic_event")
                cur.execute("""
                    INSERT INTO traffic_event (dedup_key, title, category, sources, n_sources, n_records,
                                               first_time, max_severity, lat, lon)
                    SELECT dedup_key,
                           -- ใช้ชื่อเหตุการณ์จาก Longdo ก่อน (ละเอียดกว่า) ถ้าไม่มีใช้ของ Traffy
                           (ARRAY_AGG(title ORDER BY (source = 'longdo') DESC, event_time))[1],
                           (ARRAY_AGG(category ORDER BY (source = 'longdo') DESC, event_time))[1],
                           ARRAY_AGG(DISTINCT source ORDER BY source),
                           COUNT(DISTINCT source), COUNT(*),
                           MIN(event_time), MAX(severity), AVG(lat), AVG(lon)
                    FROM traffic_record
                    WHERE dedup_key IS NOT NULL AND event_time >= NOW() - INTERVAL '30 days'
                    GROUP BY dedup_key
                """)
                print(f"traffic_event: {cur.rowcount} เหตุการณ์หลังตัดซ้ำข้ามแหล่ง")

        upsert_records(data) >> dedupe_events()

    @task
    def quarantine(data):
        print(f"ข้อมูลไม่ผ่านการตรวจคุณภาพ ไม่นำเข้าตารางหลัก ({len(data['rejected'])} แถวเสีย)")

    @task(trigger_rule="none_failed_min_one_success")
    def record_run(data):
        ctx = get_current_context()
        q = ctx["ti"].xcom_pull(task_ids="quality_check", key="quality")
        run_id = ctx["run_id"]
        states = [s["state"] for s in data["source_status"].values()]
        if not q["passed"]:
            status = "QUALITY_FAILED"
        elif all(s == "success" for s in states):
            status = "SUCCESS"
        else:
            status = "PARTIAL"  # มีบางแหล่งล่ม/ข้าม แต่รวมข้อมูลจากแหล่งที่เหลือได้
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        with hook.get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM quality_issue WHERE run_id = %s", (run_id,))
            if data["rejected"]:
                execute_values(cur, "INSERT INTO quality_issue (run_id, observed_at, source, source_id, problem) VALUES %s",
                               [(run_id, data["observed_at"], r["source"], r["source_id"], r["problem"])
                                for r in data["rejected"]])
            cur.execute("""
                INSERT INTO pipeline_run (run_id, observed_at, started_at, finished_at, source_status, n_raw,
                                          n_valid, n_rejected, quality_passed, quality_reason, branch, status)
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    finished_at = NOW(), source_status = EXCLUDED.source_status, n_raw = EXCLUDED.n_raw,
                    n_valid = EXCLUDED.n_valid, n_rejected = EXCLUDED.n_rejected,
                    quality_passed = EXCLUDED.quality_passed, quality_reason = EXCLUDED.quality_reason,
                    branch = EXCLUDED.branch, status = EXCLUDED.status
            """, (run_id, data["observed_at"], ctx["dag_run"].start_date or datetime.now(timezone.utc),
                  Json(data["source_status"]), data["n_raw"], len(data["records"]), len(data["rejected"]),
                  q["passed"], q["reason"], "load" if q["passed"] else "quarantine", status))
        print("สถานะรอบนี้:", status)

    data = transform(extract_group())
    branch = quality_check(data)
    loaded = load_group(data)
    quarantined = quarantine(data)
    branch >> [loaded, quarantined]
    [loaded, quarantined] >> record_run(data)


bkk_traffic_pipeline()

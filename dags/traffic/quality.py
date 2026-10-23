"""Transform + ตรวจคุณภาพข้อมูล"""
import os
from datetime import datetime, timedelta

from traffic.sources import SOURCES, in_bkk, now_bkk

REQUIRED = {
    "congestion": ("source", "source_id", "category", "period", "congestion_pct", "speed_kmh"),
    "incident": ("source", "source_id", "category", "title", "event_time", "lat", "lon"),
    "complaint": ("source", "source_id", "category", "event_time", "lat", "lon"),
}
MIN_VALID_ROWS = int(os.getenv("DQ_MIN_VALID_ROWS", "10"))
MAX_REJECT_RATIO = float(os.getenv("DQ_MAX_REJECT_RATIO", "0.3"))


def _parse_time(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def row_problems(r):
    probs = [f"{k} ว่าง" for k in REQUIRED.get(r.get("record_type"), ("record_type",)) if r.get(k) in (None, "")]
    if r.get("congestion_pct") is not None and not 0 <= r["congestion_pct"] <= 300:
        probs.append(f"congestion_pct ผิดช่วง ({r['congestion_pct']})")
    for k in ("speed_kmh", "free_flow_kmh"):
        if r.get(k) is not None and not 0 < r[k] <= 150:
            probs.append(f"{k} ผิดช่วง ({r[k]})")
    if r.get("severity") is not None and not 0 <= r["severity"] <= 5:
        probs.append(f"severity ผิดช่วง ({r['severity']})")
    if r.get("lat") is not None and not in_bkk(r["lat"], r["lon"]):
        probs.append(f"พิกัดอยู่นอกกรุงเทพฯ ({r['lat']}, {r['lon']})")
    if r.get("event_time"):
        try:
            if _parse_time(r["event_time"]) > now_bkk() + timedelta(days=2):
                probs.append(f"เวลาอยู่ในอนาคต ({r['event_time']})")
        except ValueError:
            probs.append(f"รูปแบบเวลาไม่ถูกต้อง ({r['event_time']})")
    return probs


def transform(raw_by_source):
    """raw_by_source: {source: [raw items]} -> (records, rejected)

    - แปลงทุกแหล่งเป็น schema เดียวกัน
    - ตัดรายการซ้ำภายในรอบ (source, source_id)
    - แยกแถวที่ไม่ผ่านกฎคุณภาพออกเป็น rejected
    """
    records, rejected, seen = [], [], set()
    for source, items in raw_by_source.items():
        for item in items or []:
            try:
                r = SOURCES[source]["parse"](item)
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                rejected.append({"source": source, "source_id": None, "problem": f"parse error: {e!r}"})
                continue
            probs = row_problems(r)
            if probs:
                rejected.append({"source": source, "source_id": r.get("source_id"), "problem": "; ".join(probs)})
                continue
            if (r["source"], r["source_id"]) in seen:
                continue
            seen.add((r["source"], r["source_id"]))
            records.append(r)
    return records, rejected


def evaluate(n_valid, n_rejected):
    """ผลตรวจระดับชุดข้อมูล -> (passed, reason)"""
    total = n_valid + n_rejected
    ratio = n_rejected / total if total else 1.0
    if n_valid < MIN_VALID_ROWS:
        return False, f"แถวที่ใช้ได้ {n_valid} < {MIN_VALID_ROWS}"
    if ratio > MAX_REJECT_RATIO:
        return False, f"สัดส่วนแถวเสีย {ratio:.0%} > {MAX_REJECT_RATIO:.0%}"
    return True, f"ผ่าน: ใช้ได้ {n_valid} แถว, เสีย {n_rejected} แถว ({ratio:.0%})"

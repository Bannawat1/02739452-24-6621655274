"""Transform + ตรวจคุณภาพข้อมูล"""
import os

from traffic.sources import SOURCES

REQUIRED = ("source", "source_id", "road", "length_m", "speed_kmh", "jam_level")
MIN_VALID_ROWS = int(os.getenv("DQ_MIN_VALID_ROWS", "10"))
MAX_REJECT_RATIO = float(os.getenv("DQ_MAX_REJECT_RATIO", "0.3"))


def row_problems(r):
    probs = [f"{k} ว่าง" for k in REQUIRED if r.get(k) in (None, "")]
    if r.get("speed_kmh") is not None and not 0 <= r["speed_kmh"] <= 150:
        probs.append(f"speed_kmh ผิดช่วง ({r['speed_kmh']})")
    if r.get("length_m") is not None and r["length_m"] <= 0:
        probs.append(f"length_m <= 0 ({r['length_m']})")
    if r.get("jam_level") is not None and not 0 <= r["jam_level"] <= 5:
        probs.append(f"jam_level ผิดช่วง ({r['jam_level']})")
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
            except (KeyError, TypeError, ValueError, ZeroDivisionError, StopIteration) as e:
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

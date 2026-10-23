"""Extract + parse ของแต่ละแหล่ง (ทุกแหล่งไม่ต้องใช้ API key)

    tomtom_index : web scraping หน้า TomTom Traffic Index กรุงเทพฯ (อ่านข้อมูลที่ฝังใน HTML, ไม่ใช้ Selenium)
                   -> ระดับรถติด (%) ของกรุงเทพฯ รายชั่วโมงทั้งสัปดาห์ / รายเดือน / ช่วงเร่งด่วน
    longdo       : Longdo Traffic event feed (JSON) -> เหตุการณ์จราจร เช่น น้ำท่วม อุบัติเหตุ งานก่อสร้าง
    traffy       : Traffy Fondue public API (JSON) -> เรื่องร้องเรียนด้านถนน/จราจร/น้ำท่วมในกรุงเทพฯ

ทุกแหล่งถูกแปลงเป็น record รูปแบบเดียวกัน (ดู RECORD_FIELDS)
PDPA: ไม่เก็บชื่อผู้รายงาน (contributor), ข้อความร้องเรียน (description) และรูปภาพ
"""
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib import robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)
TIMEOUT = 60
USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "Mozilla/5.0 (compatible; BKKTrafficEdu/1.0; university project)")
BKK = timezone(timedelta(hours=7))

# กรอบพื้นที่กรุงเทพฯ และปริมณฑลชั้นใน
BKK_BBOX = {"lat_min": 13.49, "lat_max": 13.96, "lon_min": 100.32, "lon_max": 100.94}

RECORD_FIELDS = (
    "source", "source_id", "record_type", "category", "title", "area", "period", "event_time",
    "lat", "lon", "congestion_pct", "speed_kmh", "free_flow_kmh", "severity", "dedup_key",
)


class SourceSkipped(Exception):
    """แหล่งนี้ถูกปิดไว้ -> task จะเป็นสถานะ skipped"""


def _enabled(name):
    if os.getenv(f"ENABLE_{name.upper()}", "true").lower() != "true":
        raise SourceSkipped(f"ENABLE_{name.upper()}=false")


def check_robots(url):
    """ตรวจ robots.txt ก่อนดึง ถ้าไม่อนุญาตจะไม่ดึง คืนค่า crawl-delay (ถ้ามี)"""
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    try:
        resp = requests.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
    except requests.RequestException as e:
        log.warning("อ่าน robots.txt ไม่ได้ (%s) ถือว่าไม่มีข้อห้าม", e)
        rp.parse([])
    if not rp.can_fetch(USER_AGENT, url):
        raise PermissionError(f"robots.txt ไม่อนุญาตให้ดึง {url}")
    return rp.crawl_delay(USER_AGENT) or 0


def _get(url, **params):
    delay = check_robots(url)
    if delay:
        time.sleep(min(delay, 10))  # เคารพ Crawl-delay ระหว่าง robots.txt กับหน้าข้อมูล
    resp = requests.get(url, params=params or None, timeout=TIMEOUT,
                        headers={"User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8"})
    resp.raise_for_status()
    return resp


def in_bkk(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return BKK_BBOX["lat_min"] <= lat <= BKK_BBOX["lat_max"] and BKK_BBOX["lon_min"] <= lon <= BKK_BBOX["lon_max"]


def dedup_key(event_time, lat, lon, category):
    """เหตุการณ์กลุ่มเดียวกัน วันเดียวกัน ในช่องกริด ~300 ม. เดียวกัน ถือเป็นเหตุการณ์เดียวกัน (ใช้ข้ามแหล่ง)

    หมวดของแต่ละแหล่งละเอียดไม่เท่ากัน จึงจับคู่ด้วยกลุ่มหยาบ: น้ำท่วม / ถนนและจราจร
    """
    day = str(event_time)[:10]
    group = "flood" if category == "flood" else "road"
    return f"{day}:{round(float(lat) / 0.003)}:{round(float(lon) / 0.003)}:{group}"


# ---------------- 1) TomTom Traffic Index (web scraping) ----------------
TOMTOM_URL = "https://www.tomtom.com/traffic-index/bangkok-traffic/"
_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


def _astro(v):
    """แปลงรูปแบบ props ของ Astro ([0, value] / [1, [list]]) เป็น JSON ปกติ"""
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        kind, val = v
        if kind == 1:
            return [_astro(x) for x in val]
        return _astro(val)
    if isinstance(v, dict):
        return {k: _astro(x) for k, x in v.items()}
    return v


def _json_block(text, start):
    """ตัดก้อน JSON ที่เริ่มที่ text[start] ('[' หรือ '{') โดยนับวงเล็บ (ข้ามเครื่องหมายในสตริง)"""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("หาจุดสิ้นสุดของ JSON ไม่เจอ")


def parse_tomtom_html(page):
    """ดึงก้อน "traffic" ที่ฝังอยู่ใน HTML ของหน้า Traffic Index"""
    text = html.unescape(page)
    m = re.search(r'"traffic"\s*:\s*(\[\s*0\s*,\s*\{\s*"metro")', text)
    if not m:
        raise ValueError("ไม่พบข้อมูล traffic ในหน้าเว็บ (โครงสร้างหน้าอาจเปลี่ยน)")
    return _astro(json.loads(_json_block(text, m.start(1))))


def extract_tomtom_index():
    _enabled("tomtom_index")
    traffic = parse_tomtom_html(_get(TOMTOM_URL).text)
    items = []
    for area, by_type in traffic.items():          # เช่น metro / city
        for road_type, d in by_type.items():       # เช่น all
            for kind in ("base", "am", "pm", "ampm"):
                if d.get(kind):
                    items.append({"area": area, "road_type": road_type, "kind": kind, **d[kind]})
            for kind in ("monthly", "weekHour"):
                for p in d.get(kind) or []:
                    items.append({"area": area, "road_type": road_type, "kind": kind, **p})
    log.info("TomTom Traffic Index: %d รายการ", len(items))
    return items


def _tomtom_period(kind, t):
    if kind == "weekHour":                      # "MONDAY-8" -> "1-จันทร์ 08:00" เรียงได้
        day, hour = t.split("-")
        return f"{_DAYS.index(day) + 1}-{day.title()} {int(hour):02d}:00"
    if kind == "monthly":
        return t[:7]                            # "2025-01"
    if kind in ("am", "pm"):
        return f"{kind.upper()} peak {int(t):02d}:00"
    return {"base": "ทั้งปี", "ampm": "ช่วงเร่งด่วนรวม"}[kind]


def parse_tomtom_index(it):
    t = it.get("time")
    return {
        "source": "tomtom_index",
        "source_id": f"{it['area']}:{it['road_type']}:{it['kind']}:{t or '-'}",
        "record_type": "congestion",
        "category": it["kind"],
        "title": f"ระดับรถติดกรุงเทพฯ ({it['area']}/{it['road_type']})",
        "area": "กรุงเทพมหานคร",
        "period": _tomtom_period(it["kind"], t),
        "event_time": f"{t}:00+07:00" if it["kind"] == "monthly" else None,
        "lat": None, "lon": None,
        "congestion_pct": it.get("c"),
        "speed_kmh": it.get("v"),
        "free_flow_kmh": it.get("fv"),
        "severity": None,
        "dedup_key": None,
    }


# ---------------- 2) Longdo Traffic event feed ----------------
LONGDO_URL = "https://event.longdo.com/feed/json"
_LONGDO_CATEGORY = {"flood": "flood", "rain": "flood", "accident": "accident", "construction": "roadwork",
                    "roadwork": "roadwork", "closed": "closure", "trafficjam": "traffic", "jam": "traffic"}


def extract_longdo():
    _enabled("longdo")
    events = _get(LONGDO_URL).json()
    keep = ("eid", "title", "latitude", "longitude", "type", "start", "stop", "icon", "severity")
    out = [{k: e.get(k) for k in keep} for e in events if in_bkk(e.get("latitude"), e.get("longitude"))]
    log.info("Longdo: ทั้งหมด %d เหตุการณ์, ในกรุงเทพฯ %d", len(events), len(out))
    return out


def parse_longdo(e):
    category = _LONGDO_CATEGORY.get((e.get("icon") or "").lower(), "other")
    event_time = f"{e['start']}+07:00" if e.get("start") else None
    sev = e.get("severity")
    lat, lon = float(e["latitude"]), float(e["longitude"])
    return {
        "source": "longdo",
        "source_id": str(e["eid"]),
        "record_type": "incident",
        "category": category,
        "title": e.get("title") or "",
        "area": "กรุงเทพมหานคร",
        "period": None,
        "event_time": event_time,
        "lat": lat, "lon": lon,
        "congestion_pct": None, "speed_kmh": None, "free_flow_kmh": None,
        "severity": int(sev) if str(sev).isdigit() else 0,
        "dedup_key": dedup_key(event_time, lat, lon, category) if event_time else None,
    }


# ---------------- 3) Traffy Fondue (เรื่องร้องเรียนของ กทม.) ----------------
TRAFFY_URL = "https://publicapi.traffy.in.th/share/teamchadchart/search"
TRAFFY_LIMIT = int(os.getenv("TRAFFY_LIMIT", "500"))
# ประเภทปัญหาที่ส่งผลต่อการจราจรบนถนน -> หมวดกลาง (ไม่รวมทางเท้า เพราะไม่กระทบรถ)
_TRAFFY_TYPES = {"จราจร": "traffic", "ถนน": "road", "น้ำท่วม": "flood", "สะพาน": "road"}
# ใช้เมื่อเรื่องไม่มีประเภท ห้ามใช้คำว่า "ถนน" เพราะข้อความของ Traffy มีบรรทัด "ถนน: <ชื่อถนน>" ระบุที่อยู่แทบทุกเรื่อง
_TRAFFY_KEYWORDS = {"รถติด": "traffic", "การจราจร": "traffic", "น้ำท่วม": "flood"}


def _traffy_category(item):
    for t in item.get("problem_type_abdul") or []:
        if t in _TRAFFY_TYPES:
            return _TRAFFY_TYPES[t]
    # ไม่มีประเภท -> ดูคำสำคัญในข้อความ (ใช้จัดหมวดเท่านั้น ไม่ได้เก็บข้อความ)
    desc = item.get("description") or ""
    for kw, cat in _TRAFFY_KEYWORDS.items():
        if kw in desc:
            return cat
    return None


def extract_traffy():
    _enabled("traffy")
    data = _get(TRAFFY_URL, limit=TRAFFY_LIMIT).json()
    out = []
    for it in data.get("results", []):
        cat = _traffy_category(it)
        coords = it.get("coords") or [None, None]
        if not cat or not in_bkk(coords[1], coords[0]):
            continue
        address = it.get("address") or ""
        out.append({
            "ticket_id": it.get("ticket_id"),
            "category": cat,
            "problem_type": ", ".join(t for t in (it.get("problem_type_abdul") or []) if t),
            "district": next((w for w in address.split() if w.startswith("เขต")), address[:60]),
            "lon": coords[0], "lat": coords[1],
            "timestamp": it.get("timestamp"),
            "state": it.get("state"),
        })
    log.info("Traffy: ได้ %d เรื่อง, เกี่ยวกับถนน/จราจรในกรุงเทพฯ %d", len(data.get("results", [])), len(out))
    return out


def parse_traffy(it):
    ts = it.get("timestamp") or ""
    event_time = ts.replace(" ", "T", 1).replace("+00", "+00:00") if ts.endswith("+00") else ts.replace(" ", "T", 1)
    lat, lon = float(it["lat"]), float(it["lon"])
    return {
        "source": "traffy",
        "source_id": str(it["ticket_id"]),
        "record_type": "complaint",
        "category": it["category"],
        "title": f"ร้องเรียน{(': ' + it['problem_type']) if it.get('problem_type') else ''} ({it.get('state') or '-'})",
        "area": it.get("district") or "",
        "period": None,
        "event_time": event_time or None,
        "lat": lat, "lon": lon,
        "congestion_pct": None, "speed_kmh": None, "free_flow_kmh": None,
        "severity": None,
        "dedup_key": dedup_key(event_time, lat, lon, it["category"]) if event_time else None,
    }


SOURCES = {
    "tomtom_index": {"extract": extract_tomtom_index, "parse": parse_tomtom_index, "kind": "web scraping"},
    "longdo": {"extract": extract_longdo, "parse": parse_longdo, "kind": "JSON feed"},
    "traffy": {"extract": extract_traffy, "parse": parse_traffy, "kind": "public API"},
}


def now_bkk():
    return datetime.now(BKK)

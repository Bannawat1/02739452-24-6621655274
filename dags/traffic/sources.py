"""Extract + parse ของแต่ละแหล่ง

    waze    : scrape ข้อมูลรถติดจากหน้า Waze Live Map (ไม่ต้องใช้ key, ไม่ใช้ Selenium)
    tomtom  : TomTom Routing API (ต้องมี TOMTOM_API_KEY)
    here    : HERE Routing API v8 (ต้องมี HERE_API_KEY)

ทุกแหล่งถูกแปลงเป็น record รูปแบบเดียวกัน:
    source, source_id, road, road_key, length_m, speed_kmh, delay_s, jam_level (0-5), lat, lon
ข้อมูลที่ดึงเป็นข้อมูลถนน/การจราจรเท่านั้น ไม่มีข้อมูลส่วนบุคคล (PDPA)
"""
import logging
import os
from urllib import robotparser
from urllib.parse import urlparse

import requests

from traffic.corridors import BKK_BBOX, CORRIDORS, road_key

log = logging.getLogger(__name__)
TIMEOUT = 30
USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "Mozilla/5.0 (compatible; BKKTrafficEdu/1.0; university project)")


class SourceSkipped(Exception):
    """แหล่งนี้ถูกปิด/ไม่มี key -> task จะเป็นสถานะ skipped"""


def check_robots(url):
    """ตรวจ robots.txt ก่อน scrape ถ้าไม่อนุญาตจะไม่ดึง"""
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    try:
        resp = requests.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
    except requests.RequestException as e:
        log.warning("อ่าน robots.txt ไม่ได้ (%s) ถือว่าไม่มีข้อห้าม", e)
        rp.parse([])
    if not rp.can_fetch(USER_AGENT, url):
        raise PermissionError(f"robots.txt ไม่อนุญาตให้ดึง {url}")


def level_from_tti(tti):
    """แปลง Travel Time Index เป็นระดับ 0-5 แบบเดียวกับ Waze"""
    if tti < 1.2:
        return 1
    if tti < 1.5:
        return 2
    if tti < 2.0:
        return 3
    return 4


def _route_record(source, corridor, distance_m, travel_s, free_s):
    tti = max(travel_s / free_s, 1.0) if free_s else 1.0
    (olat, olon), (dlat, dlon) = corridor["origin"], corridor["dest"]
    return {
        "source": source,
        "source_id": corridor["id"],
        "road": corridor["road"],
        "road_key": road_key(corridor["road"]),
        "length_m": int(distance_m),
        "speed_kmh": round(distance_m / travel_s * 3.6, 2) if travel_s else None,
        "delay_s": max(int(travel_s - free_s), 0),
        "jam_level": level_from_tti(tti),
        "lat": round((olat + dlat) / 2, 6),
        "lon": round((olon + dlon) / 2, 6),
    }


# ---------------- Waze (web scraping) ----------------
WAZE_PAGE = "https://www.waze.com/live-map"
WAZE_DATA = "https://www.waze.com/live-map/api/georss"


def extract_waze():
    if os.getenv("ENABLE_WAZE", "true").lower() != "true":
        raise SourceSkipped("ENABLE_WAZE=false")
    params = {**BKK_BBOX, "env": "row", "types": "traffic"}
    check_robots(WAZE_DATA)
    resp = requests.get(WAZE_DATA, params=params, timeout=TIMEOUT,
                        headers={"User-Agent": USER_AGENT, "Referer": WAZE_PAGE, "Accept": "application/json"})
    resp.raise_for_status()
    jams = resp.json().get("jams", [])
    # เก็บเฉพาะฟิลด์ที่ใช้ (ตัดเส้น polyline ให้เหลือจุดกลาง เพื่อลดขนาด XCom)
    out = []
    for j in jams:
        line = j.get("line") or []
        mid = line[len(line) // 2] if line else {}
        out.append({k: j.get(k) for k in ("uuid", "street", "city", "level", "speedKMH", "length", "delay")}
                   | {"lat": mid.get("y"), "lon": mid.get("x")})
    log.info("Waze: ได้ %d jams", len(out))
    return out


def parse_waze(item):
    delay = item.get("delay")
    return {
        "source": "waze",
        "source_id": str(item["uuid"]),
        "road": item.get("street") or f"(ไม่ระบุชื่อถนน) {item.get('city') or ''}".strip(),
        "road_key": road_key(item.get("street")),
        "length_m": item.get("length"),
        "speed_kmh": item.get("speedKMH"),
        "delay_s": None if delay is None or delay < 0 else delay,  # -1 = ถนนปิด
        "jam_level": item.get("level"),
        "lat": item.get("lat"),
        "lon": item.get("lon"),
    }


# ---------------- TomTom Routing API ----------------
def _key(env):
    key = os.getenv(env, "").strip()
    if not key:
        raise SourceSkipped(f"ไม่มี {env}")
    return key


def extract_tomtom():
    key = _key("TOMTOM_API_KEY")
    out = []
    for c in CORRIDORS:
        (olat, olon), (dlat, dlon) = c["origin"], c["dest"]
        resp = requests.get(
            f"https://api.tomtom.com/routing/1/calculateRoute/{olat},{olon}:{dlat},{dlon}/json",
            params={"key": key, "traffic": "true", "computeTravelTimeFor": "all",
                    "routeRepresentation": "summaryOnly", "travelMode": "car"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        out.append({"corridor_id": c["id"], "summary": resp.json()["routes"][0]["summary"]})
    return out


def parse_tomtom(item):
    s = item["summary"]
    c = next(c for c in CORRIDORS if c["id"] == item["corridor_id"])
    return _route_record("tomtom", c, s["lengthInMeters"], s["travelTimeInSeconds"],
                         s["noTrafficTravelTimeInSeconds"])


# ---------------- HERE Routing API v8 ----------------
def extract_here():
    key = _key("HERE_API_KEY")
    out = []
    for c in CORRIDORS:
        (olat, olon), (dlat, dlon) = c["origin"], c["dest"]
        resp = requests.get(
            "https://router.hereapi.com/v8/routes",
            params={"apiKey": key, "transportMode": "car", "origin": f"{olat},{olon}",
                    "destination": f"{dlat},{dlon}", "return": "summary"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        out.append({"corridor_id": c["id"],
                    "sections": [sec["summary"] for sec in resp.json()["routes"][0]["sections"]]})
    return out


def parse_here(item):
    secs = item["sections"]
    c = next(c for c in CORRIDORS if c["id"] == item["corridor_id"])
    return _route_record("here", c, sum(s["length"] for s in secs), sum(s["duration"] for s in secs),
                         sum(s["baseDuration"] for s in secs))


SOURCES = {
    "waze": {"extract": extract_waze, "parse": parse_waze, "kind": "web scraping"},
    "tomtom": {"extract": extract_tomtom, "parse": parse_tomtom, "kind": "API"},
    "here": {"extract": extract_here, "parse": parse_here, "kind": "API"},
}

"""รัน: pytest tests"""
import json
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))
sys.path.insert(0, os.path.dirname(__file__))

from sample_responses import LONGDO, TOMTOM_HTML, TRAFFY  # noqa: E402
from traffic import quality, sources  # noqa: E402


class Resp:
    def __init__(self, text="", status=200, payload=None):
        self.text, self.status_code, self._p = text, status, payload

    def json(self):
        return self._p if self._p is not None else json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise sources.requests.HTTPError(self.status_code)


def fake_get(url, params=None, **kw):
    if url.endswith("robots.txt"):
        return Resp("User-agent: *\nCrawl-delay: 0\nDisallow: /admin/")
    if "tomtom" in url:
        return Resp(TOMTOM_HTML)
    if "longdo" in url:
        return Resp(payload=LONGDO)
    return Resp(payload=TRAFFY)


def extract_all():
    with mock.patch.object(sources.requests, "get", fake_get):
        return {name: s["extract"]() for name, s in sources.SOURCES.items()}


def test_tomtom_scraping_parses_embedded_json():
    items = extract_all()["tomtom_index"]
    assert len(items) == 4 + 2 + 3  # base/am/pm/ampm + monthly 2 + weekHour 3
    rec = {r["source_id"]: r for r in map(sources.parse_tomtom_index, items)}
    assert rec["metro:all:weekHour:FRIDAY-17"]["congestion_pct"] == 105.2
    assert rec["metro:all:weekHour:MONDAY-8"]["period"] == "1-Monday 08:00"
    assert rec["metro:all:monthly:2025-01-01T00:00"]["period"] == "2025-01"


def test_filters_bangkok_and_drops_personal_data():
    raw = extract_all()
    assert [e["eid"] for e in raw["longdo"]] == ["990001", "990002"]  # นอกกรุงเทพฯ ถูกกรองทิ้ง
    assert all("contributor" not in e for e in raw["longdo"])
    assert [t["ticket_id"] for t in raw["traffy"]] == ["2026-AAAA01", "2026-AAAA02"]  # เรื่องขยะถูกกรองทิ้ง
    assert all("description" not in t and "photo_url" not in t for t in raw["traffy"])


def test_transform_same_schema_and_cross_source_dedup_key():
    records, rejected = quality.transform(extract_all())
    assert not rejected
    assert {tuple(sorted(r)) for r in records} == {tuple(sorted(sources.RECORD_FIELDS))}
    by_id = {r["source_id"]: r for r in records}
    # น้ำท่วมจุดเดียวกันจาก Longdo และ Traffy วันเดียวกัน -> dedup_key เดียวกัน
    assert by_id["990001"]["dedup_key"] == by_id["2026-AAAA01"]["dedup_key"]
    assert by_id["990002"]["dedup_key"] != by_id["2026-AAAA02"]["dedup_key"]


def test_robots_disallow_blocks():
    def robots_get(url, **kw):
        return Resp("User-agent: *\nDisallow: /")
    with mock.patch.object(sources.requests, "get", robots_get):
        try:
            sources.extract_longdo()
            raise AssertionError("ควรถูก robots.txt บล็อก")
        except PermissionError:
            pass


def test_layout_change_is_reported():
    try:
        sources.parse_tomtom_html("<html>no data</html>")
        raise AssertionError("ควรแจ้งว่าไม่พบข้อมูล")
    except ValueError:
        pass


def test_quality_rules_and_branch_decision():
    bad = sources.parse_longdo({**LONGDO[2], "latitude": "18.79", "longitude": "98.98"})  # เชียงใหม่
    assert "นอกกรุงเทพฯ" in quality.row_problems(bad)[0]
    bad2 = {**sources.parse_tomtom_index({"area": "metro", "road_type": "all", "kind": "base",
                                          "c": 999, "v": 0, "fv": 50})}
    assert len(quality.row_problems(bad2)) == 2
    assert quality.evaluate(100, 5)[0] is True
    assert quality.evaluate(100, 80)[0] is False
    assert quality.evaluate(3, 0)[0] is False

"""รัน: pytest tests"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))
sys.path.insert(0, os.path.dirname(__file__))

from sample_responses import HERE, TOMTOM, WAZE  # noqa: E402
from traffic import quality, sources  # noqa: E402
from traffic.corridors import CORRIDORS, road_key  # noqa: E402


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, ""

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise sources.requests.HTTPError(self.status_code)


def fake_get(url, params=None, **kw):
    if url.endswith("robots.txt"):
        return Resp(None, 404)
    if "waze" in url:
        return Resp(WAZE)
    return Resp(TOMTOM if "tomtom" in url else HERE)


def test_road_key_matches_across_sources():
    assert road_key("ถ.สุขุมวิท") == road_key("Sukhumvit Rd") == road_key("สุขุมวิท")
    assert road_key("Rama IV Rd") == road_key("พระรามที่ 4") == road_key("ถนนพระราม 4")


def test_extract_and_transform_all_sources():
    env = {"TOMTOM_API_KEY": "x", "HERE_API_KEY": "x"}
    with mock.patch.dict(os.environ, env), mock.patch.object(sources.requests, "get", fake_get):
        raw = {name: s["extract"]() for name, s in sources.SOURCES.items()}
    assert len(raw["waze"]) == 4 and len(raw["tomtom"]) == len(CORRIDORS)
    records, rejected = quality.transform(raw)
    assert not rejected
    assert {tuple(sorted(r)) for r in records} == {tuple(sorted(records[0]))}  # schema เดียวกัน
    waze = {r["source_id"]: r for r in records if r["source"] == "waze"}
    assert waze["1004"]["delay_s"] is None and waze["1004"]["jam_level"] == 5
    assert waze["1003"]["road_key"] == ""
    tt = next(r for r in records if r["source"] == "tomtom")
    assert tt["delay_s"] == 230 and tt["jam_level"] == 3  # TTI 540/310 = 1.74


def test_missing_key_skips_source():
    with mock.patch.dict(os.environ, {"TOMTOM_API_KEY": ""}):
        try:
            sources.extract_tomtom()
            raise AssertionError("ควร skip")
        except sources.SourceSkipped:
            pass


def test_robots_disallow_blocks_scraping():
    def robots_get(url, **kw):
        r = Resp(None)
        r.text = "User-agent: *\nDisallow: /live-map/api/"
        return r
    with mock.patch.object(sources.requests, "get", robots_get):
        try:
            sources.extract_waze()
            raise AssertionError("ควรถูก robots.txt บล็อก")
        except PermissionError:
            pass


def test_quality_rules_and_branch_decision():
    bad = {"waze": [{"uuid": 1, "street": "x", "level": 9, "speedKMH": 500, "length": 0, "delay": 1}]}
    records, rejected = quality.transform(bad)
    assert not records and "speed_kmh ผิดช่วง" in rejected[0]["problem"]
    assert quality.evaluate(100, 5)[0] is True
    assert quality.evaluate(100, 80)[0] is False
    assert quality.evaluate(3, 0)[0] is False

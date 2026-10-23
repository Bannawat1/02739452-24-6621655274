"""ตัวอย่าง response (ตัดให้สั้น) ตามรูปแบบของแต่ละแหล่ง ใช้สำหรับเทสต์"""

WAZE = {"jams": [
    {"uuid": 1001, "street": "ถ.สุขุมวิท", "city": "กรุงเทพมหานคร", "level": 4, "speedKMH": 6.2,
     "length": 820, "delay": 410, "line": [{"x": 100.560, "y": 13.737}, {"x": 100.565, "y": 13.734}]},
    {"uuid": 1002, "street": "Rama IV Rd", "city": "Bangkok", "level": 3, "speedKMH": 11.5,
     "length": 640, "delay": 190, "line": [{"x": 100.54, "y": 13.73}]},
    {"uuid": 1003, "street": None, "city": "Bangkok", "level": 2, "speedKMH": 18.0,
     "length": 300, "delay": 40, "line": []},
    {"uuid": 1004, "street": "ถนนพหลโยธิน", "level": 5, "speedKMH": 0, "length": 200, "delay": -1,
     "line": [{"x": 100.55, "y": 13.80}]},
]}

TOMTOM = {"routes": [{"summary": {
    "lengthInMeters": 2650, "travelTimeInSeconds": 540, "trafficDelayInSeconds": 230,
    "noTrafficTravelTimeInSeconds": 310}}]}

HERE = {"routes": [{"id": "x", "sections": [
    {"id": "s1", "type": "vehicle", "summary": {"duration": 400, "length": 1500, "baseDuration": 210}},
    {"id": "s2", "type": "vehicle", "summary": {"duration": 120, "length": 1100, "baseDuration": 95}},
]}]}

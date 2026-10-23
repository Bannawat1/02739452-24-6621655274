"""ตัวอย่างข้อมูลจริงจากแต่ละแหล่ง (ตัดให้สั้น) ใช้สำหรับเทสต์"""
import html
import json

# --- TomTom Traffic Index: ข้อมูลฝังอยู่ใน HTML ในรูปแบบ props ของ Astro และถูก escape เป็น &quot;
_TRAFFIC = ('{"traffic":[0,{"metro":[0,{"all":[0,{'
            '"base":[0,{"c":[0,51],"v":[0,35.5],"fv":[0,53.6],"s":[0,9636865030.547]}],'
            '"am":[0,{"time":[0,"7"],"c":[0,74.8],"v":[0,30.5],"fv":[0,53.3],"s":[0,1525485.65]}],'
            '"pm":[0,{"time":[0,"18"],"c":[0,91.8],"v":[0,27.4],"fv":[0,52.6],"s":[0,1718438.99]}],'
            '"ampm":[0,{"c":[0,83.8],"v":[0,28.7],"fv":[0,52.9],"s":[0,846664333.768]}],'
            '"monthly":[1,[[0,{"time":[0,"2025-01-01T00:00"],"c":[0,47.1],"v":[0,36.7],"fv":[0,54.1]}],'
            '[0,{"time":[0,"2025-02-01T00:00"],"c":[0,51.8],"v":[0,35.5],"fv":[0,53.9]}]]],'
            '"weekHour":[1,[[0,{"time":[0,"FRIDAY-17"],"c":[0,105.2],"v":[0,26],"fv":[0,53.4]}],'
            '[0,{"time":[0,"MONDAY-8"],"c":[0,75.4],"v":[0,30.3],"fv":[0,53.2]}],'
            '[0,{"time":[0,"MONDAY-3"],"c":[0,2.1],"v":[0,50.3],"fv":[0,51.4]}]]]}]}]}],'
            '"labels":[0,{"liveTraffic":[0,"Live traffic"]}]}')
TOMTOM_HTML = f'<html><body><astro-island props="{html.escape(_TRAFFIC)}"></astro-island></body></html>'

# --- Longdo event feed (2 รายการแรกเป็นของจริงนอกกรุงเทพฯ, รายการที่ 3-4 อยู่ในกรุงเทพฯ)
LONGDO = [
    {"eid": "984997", "title": "น้ำท่วมทางหลวง 32 ช่วงนครหลวง - อ่างทอง (ผ่านได้)", "description": "...",
     "latitude": "14.515069156072", "longitude": "100.51380276163", "type": "6",
     "start": "2026-10-24 11:50:12", "stop": "2026-10-24 14:00:25", "contributor": "DOH Admin",
     "icon": "flood", "showlevel": 8, "severity": ""},
    {"eid": "985099", "title": "ฝนตก ต.ดงขี้เหล็ก", "latitude": "14.151742", "longitude": "101.409774",
     "type": "5", "start": "2026-10-23 14:08:06", "stop": "2026-10-23 15:08:06", "contributor": "tdgs7c4fh6",
     "icon": "rain", "showlevel": 12, "severity": 1},
    {"eid": "990001", "title": "น้ำท่วมขัง ถ.เสนานิคม 1", "latitude": "13.83490", "longitude": "100.58230",
     "type": "6", "start": "2026-10-23 08:10:00", "stop": "2026-10-23 12:00:00", "contributor": "someone",
     "icon": "flood", "showlevel": 10, "severity": 2},
    {"eid": "990002", "title": "อุบัติเหตุ ถ.พระราม 4", "latitude": "13.7228", "longitude": "100.5603",
     "type": "1", "start": "2026-10-23 09:00:00", "stop": "2026-10-23 10:00:00", "contributor": "someone",
     "icon": "accident", "showlevel": 10, "severity": 3},
]

# --- Traffy Fondue (รายการแรกเป็นของจริง: ปัญหาขยะ ไม่เกี่ยวกับจราจร จึงต้องถูกกรองทิ้ง)
TRAFFY = {"status": True, "total": 1518633, "results": [
    {"type": None, "org": "กรุงเทพมหานคร",
     "description": "ปัญหา: ตลอดทั้งซอยดังกล่าว พนักงานเก็บขนขยะมูลฝอยไม่เข้าดำเนินการเก็บ...\nซอย: เสนานิคม 1 ที่ 11\nถนน: เสนานิคม 1\nเขต: จตุจักร",
     "ticket_id": "2026-7K7NCK", "coords": ["100.58238", "13.83483"], "photo_url": "https://example/x.jpg",
     "after_photo": "", "address": "แขวงเสนานิคม เขตจตุจักร กรุงเทพมหานคร",
     "timestamp": "2026-10-23 07:30:21.965339+00", "problem_type_abdul": [""], "star": None,
     "count_reopen": "0", "note": None, "state": "รอรับเรื่อง", "last_activity": "2026-10-23 07:30:21.965339+00"},
    {"type": None, "org": "กรุงเทพมหานคร", "description": "น้ำท่วมขังผิวจราจร เบอร์โทร 08x-xxx-xxxx",
     "ticket_id": "2026-AAAA01", "coords": ["100.58225", "13.83495"], "photo_url": "", "after_photo": "",
     "address": "แขวงเสนานิคม เขตจตุจักร กรุงเทพมหานคร", "timestamp": "2026-10-23 03:15:00.000000+00",
     "problem_type_abdul": ["น้ำท่วม"], "state": "กำลังดำเนินการ"},
    {"type": None, "org": "กรุงเทพมหานคร", "description": "ถนนเป็นหลุมบ่อ",
     "ticket_id": "2026-AAAA02", "coords": ["100.5300", "13.7300"], "photo_url": "", "after_photo": "",
     "address": "แขวงสีลม เขตบางรัก กรุงเทพมหานคร", "timestamp": "2026-10-22 10:00:00.000000+00",
     "problem_type_abdul": ["ถนน"], "state": "เสร็จสิ้น"},
]}

"""ช่วงถนนที่ใช้วัดเวลาเดินทางด้วย TomTom / HERE และกรอบพื้นที่สำหรับ Waze

`road` ต้องตรงกับชื่อถนนที่ Waze ใช้ (หลังผ่าน road_key) เพื่อให้ตัดรายการซ้ำข้ามแหล่งได้
พิกัดเป็นค่าประมาณ ตรวจบน Google Maps ได้ว่าต้นทาง/ปลายทางอยู่บนถนนที่ต้องการ
"""
import re

# กรอบพื้นที่กรุงเทพฯ (ใช้กับ Waze)
BKK_BBOX = {"top": 13.95, "bottom": 13.55, "left": 100.33, "right": 100.93}

CORRIDORS = [
    {"id": "sukhumvit_asok_thonglo", "road": "สุขุมวิท", "origin": (13.7370, 100.5603), "dest": (13.7246, 100.5785)},
    {"id": "sukhumvit_nana_asok", "road": "สุขุมวิท", "origin": (13.7404, 100.5550), "dest": (13.7370, 100.5603)},
    {"id": "rama4_samyan_khlongtoei", "road": "พระรามที่ 4", "origin": (13.7325, 100.5290), "dest": (13.7228, 100.5603)},
    {"id": "sathorn_surasak_lumphini", "road": "สาทรเหนือ", "origin": (13.7194, 100.5216), "dest": (13.7256, 100.5455)},
    {"id": "silom_saladaeng_chongnonsi", "road": "สีลม", "origin": (13.7286, 100.5345), "dest": (13.7236, 100.5296)},
    {"id": "phahon_saphankhwai_ladprao", "road": "พหลโยธิน", "origin": (13.7937, 100.5497), "dest": (13.8160, 100.5617)},
    {"id": "ladprao_5yaek_chokchai4", "road": "ลาดพร้าว", "origin": (13.8160, 100.5617), "dest": (13.7953, 100.5958)},
    {"id": "ratchada_rama9_huaikhwang", "road": "รัชดาภิเษก", "origin": (13.7578, 100.5652), "dest": (13.7787, 100.5737)},
    {"id": "phetchaburi_pratunam_asok", "road": "เพชรบุรี", "origin": (13.7510, 100.5405), "dest": (13.7480, 100.5630)},
    {"id": "vibhavadi_dindaeng_ladprao", "road": "วิภาวดีรังสิต", "origin": (13.7700, 100.5530), "dest": (13.8160, 100.5590)},
    {"id": "rama9_rca_rama9", "road": "พระรามที่ 9", "origin": (13.7520, 100.5800), "dest": (13.7578, 100.5652)},
    {"id": "ratchadamri_pratunam_ratchaprasong", "road": "ราชดำริ", "origin": (13.7520, 100.5400), "dest": (13.7440, 100.5400)},
    {"id": "phayathai_victory_siam", "road": "พญาไท", "origin": (13.7630, 100.5370), "dest": (13.7470, 100.5320)},
    {"id": "ramkhamhaeng_rama9_bangkapi", "road": "รามคำแหง", "origin": (13.7520, 100.6000), "dest": (13.7650, 100.6430)},
    {"id": "srinakarin_bangna_sinakarin", "road": "ศรีนครินทร์", "origin": (13.6690, 100.6470), "dest": (13.7100, 100.6460)},
]

# ชื่ออังกฤษที่ Waze อาจใช้ -> ชื่อไทย
_EN_TH = {
    "sukhumvit": "สุขุมวิท", "rama4": "พระรามที่4", "ramaiv": "พระรามที่4", "rama9": "พระรามที่9",
    "ramaix": "พระรามที่9", "sathonnuea": "สาทรเหนือ", "northsathorn": "สาทรเหนือ", "silom": "สีลม",
    "phahonyothin": "พหลโยธิน", "phaholyothin": "พหลโยธิน", "ladprao": "ลาดพร้าว", "latphrao": "ลาดพร้าว",
    "ratchadaphisek": "รัชดาภิเษก", "phetchaburi": "เพชรบุรี", "newphetchaburi": "เพชรบุรีตัดใหม่",
    "vibhavadirangsit": "วิภาวดีรังสิต", "viphavadirangsit": "วิภาวดีรังสิต", "ratchadamri": "ราชดำริ",
    "phayathai": "พญาไท", "ramkhamhaeng": "รามคำแหง", "srinagarindra": "ศรีนครินทร์", "srinakarin": "ศรีนครินทร์",
}


def road_key(name):
    """ทำชื่อถนนให้เป็นรูปแบบเดียว เพื่อใช้จับคู่ข้ามแหล่ง เช่น 'ถ.พระราม 4', 'Rama IV Rd' -> 'พระรามที่4'"""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"^(ถนน|ถ\.)\s*", "", s)
    s = re.sub(r"\b(road|rd\.?|street|st\.?)$", "", s)
    s = re.sub(r"[\s\.\-]", "", s)
    s = s.replace("พระราม", "พระรามที่").replace("ที่ที่", "ที่")
    return _EN_TH.get(s, s)

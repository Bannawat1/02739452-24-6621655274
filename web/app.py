import pandas as pd
import plotly.express as px
import streamlit as st

from db import LEVEL_COLOR, LEVEL_LABEL, query
from theme import SOURCE_COLOR, apply_theme, band, hero

st.set_page_config(page_title="Bangkok Traffic", page_icon="🚦", layout="wide")
apply_theme()
hero("Bangkok Traffic · Near real-time", "ความหนาแน่นการจราจรกรุงเทพฯ",
     "รวมข้อมูลจาก Waze Live Map (web scraping), TomTom Routing API และ HERE Routing API "
     "ด้วย Apache Airflow ทุก 15 นาที · ระดับความหนาแน่น 0–5 (0 โล่ง … 4 ติดขัด, 5 ถนนปิด)")

# ---------------- ตัวกรอง ----------------
runs = query("SELECT DISTINCT observed_at FROM traffic_record ORDER BY observed_at DESC")
if runs.empty:
    st.info("ยังไม่มีข้อมูล เปิด Airflow (http://localhost:8080) แล้ว trigger DAG `bkk_traffic_pipeline` จากนั้นรีเฟรชหน้านี้")
    st.stop()
runs["label"] = pd.to_datetime(runs["observed_at"]).dt.tz_convert("Asia/Bangkok").dt.strftime("%d/%m/%Y %H:%M")

with st.sidebar:
    st.header("ตัวกรอง")
    run_label = st.selectbox("รอบข้อมูล (สำหรับแผนที่/อันดับ)", runs["label"])
    run_at = runs.loc[runs["label"] == run_label, "observed_at"].iloc[0]
    hours = st.select_slider("ช่วงเวลาของกราฟแนวโน้ม", [3, 6, 12, 24, 72, 168], value=24,
                             format_func=lambda h: f"{h} ชม." if h < 48 else f"{h // 24} วัน")
    sources = st.multiselect("แหล่งข้อมูล", ["waze", "tomtom", "here"], default=["waze", "tomtom", "here"])
    min_level = st.slider("ระดับความหนาแน่นขั้นต่ำ", 0, 5, 0)
    road_search = st.text_input("ค้นหาชื่อถนน", placeholder="เช่น สุขุมวิท")

if not sources:
    st.warning("เลือกแหล่งข้อมูลอย่างน้อย 1 แหล่ง")
    st.stop()

rec = query("""
    SELECT source, source_id, road, road_key, length_m, speed_kmh::float AS speed_kmh, delay_s,
           jam_level, lat, lon
    FROM traffic_record WHERE observed_at = %(t)s
""", t=run_at)
rec = rec[rec["source"].isin(sources) & (rec["jam_level"] >= min_level)]
if road_search:
    rec = rec[rec["road"].str.contains(road_search, case=False, na=False)]

roads = query("""
    SELECT road, road_key, sources, n_sources, n_records, avg_speed_kmh::float AS avg_speed_kmh,
           max_jam_level, total_delay_s, total_length_m
    FROM road_status WHERE observed_at = %(t)s
""", t=run_at)
roads = roads[roads["sources"].apply(lambda s: bool(set(s) & set(sources))) & (roads["max_jam_level"] >= min_level)]
if road_search:
    roads = roads[roads["road"].str.contains(road_search, case=False, na=False)]

# ---------------- KPI ----------------
k = st.columns(5)
k[0].metric("รายการ (รอบนี้)", f"{len(rec):,}")
k[1].metric("ถนนหลังตัดซ้ำ", f"{len(roads):,}")
k[2].metric("ความเร็วเฉลี่ย", f"{rec['speed_kmh'].mean():.1f} กม./ชม." if len(rec) else "-")
k[3].metric("ถนนที่ติดขัด (ระดับ ≥ 3)", f"{(roads['max_jam_level'] >= 3).sum():,}")
k[4].metric("ข้อมูลสะสมทั้งหมด",
            f"{query('SELECT COUNT(*) AS n FROM traffic_record')['n'].iloc[0]:,} รายการ")

# ---------------- แผนที่ + อันดับ ----------------
left, right = st.columns([3, 2])
with left:
    st.subheader("แผนที่จุดรถติด")
    m = rec.dropna(subset=["lat", "lon"]).copy()
    m["ระดับ"] = m["jam_level"].map(LEVEL_LABEL)
    fig = px.scatter_mapbox(m, lat="lat", lon="lon", color="ระดับ", size=m["jam_level"] + 1, size_max=12,
                         hover_name="road", hover_data={"source": True, "speed_kmh": True, "lat": False,
                                                        "lon": False},
                         color_discrete_map={LEVEL_LABEL[k]: v for k, v in LEVEL_COLOR.items()},
                         category_orders={"ระดับ": list(LEVEL_LABEL.values())},
                         mapbox_style="carto-positron", zoom=10, center={"lat": 13.75, "lon": 100.56})
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("15 ถนนที่ติดที่สุด")
    top = roads.sort_values(["max_jam_level", "total_delay_s"], ascending=False).head(15)
    top["ระดับ"] = top["max_jam_level"].map(LEVEL_LABEL)
    fig = px.bar(top.iloc[::-1], x="total_delay_s", y="road", color="ระดับ", orientation="h",
                 color_discrete_map={LEVEL_LABEL[k]: v for k, v in LEVEL_COLOR.items()},
                 labels={"total_delay_s": "ความล่าช้ารวม (วินาที)", "road": ""})
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- แนวโน้ม + สัดส่วน ----------------
band("แนวโน้มและการกระจายตัวของความหนาแน่น · เลือกช่วงเวลาและแหล่งข้อมูลได้จากแถบด้านซ้าย")
a, b = st.columns([3, 2])
with a:
    st.subheader("ความเร็วเฉลี่ยตามเวลา แยกตามแหล่ง")
    trend = query("""
        SELECT observed_at, source, AVG(speed_kmh)::float AS speed_kmh, COUNT(*) AS n
        FROM traffic_record WHERE observed_at >= NOW() - make_interval(hours => %(h)s)
        GROUP BY 1, 2 ORDER BY 1
    """, h=hours)
    trend = trend[trend["source"].isin(sources)]
    trend["observed_at"] = pd.to_datetime(trend["observed_at"]).dt.tz_convert("Asia/Bangkok")
    fig = px.line(trend, x="observed_at", y="speed_kmh", color="source", markers=True,
                  color_discrete_map=SOURCE_COLOR,
                  labels={"observed_at": "เวลา", "speed_kmh": "กม./ชม.", "source": "แหล่ง"})
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
with b:
    st.subheader("สัดส่วนระดับความหนาแน่น")
    dist = rec.groupby(["jam_level", "source"]).size().reset_index(name="n")
    dist["ระดับ"] = dist["jam_level"].map(LEVEL_LABEL)
    fig = px.bar(dist, x="ระดับ", y="n", color="source", barmode="stack", color_discrete_map=SOURCE_COLOR,
                 category_orders={"ระดับ": list(LEVEL_LABEL.values())},
                 labels={"n": "จำนวนรายการ", "source": "แหล่ง"})
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- ตาราง ----------------
band("ข้อมูลดิบจากทุกแหล่ง และข้อมูลรายถนนหลังรวมรายการซ้ำข้ามแหล่งแล้ว")
st.subheader("ตารางข้อมูล")
t1, t2 = st.tabs(["รายถนน (ตัดซ้ำข้ามแหล่งแล้ว)", "ข้อมูลรวมทุกแหล่ง"])
with t1:
    show = roads.sort_values("max_jam_level", ascending=False).copy()
    show["ระดับ"] = show["max_jam_level"].map(LEVEL_LABEL)
    show["sources"] = show["sources"].apply(", ".join)
    st.dataframe(show[["road", "ระดับ", "avg_speed_kmh", "total_delay_s", "total_length_m", "n_records", "sources"]],
                 hide_index=True, use_container_width=True,
                 column_config={"road": "ถนน", "avg_speed_kmh": "ความเร็วเฉลี่ย (กม./ชม.)",
                                "total_delay_s": "ล่าช้ารวม (วิ)", "total_length_m": "ระยะรวม (ม.)",
                                "n_records": "จำนวนรายการ", "sources": "แหล่งที่รายงาน"})
with t2:
    show = rec.sort_values("jam_level", ascending=False).copy()
    show["ระดับ"] = show["jam_level"].map(LEVEL_LABEL)
    st.dataframe(show[["source", "road", "ระดับ", "speed_kmh", "delay_s", "length_m", "source_id"]],
                 hide_index=True, use_container_width=True)

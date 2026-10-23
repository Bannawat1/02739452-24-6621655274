import pandas as pd
import plotly.express as px
import streamlit as st

from db import query
from theme import CATEGORY_COLOR, SOURCE_COLOR, apply_theme, band, hero

st.set_page_config(page_title="Bangkok Traffic", page_icon="🚦", layout="wide")
apply_theme()
hero("Bangkok Traffic", "ความหนาแน่นการจราจรกรุงเทพฯ",
     "รวมข้อมูลจาก TomTom Traffic Index (web scraping), Longdo Traffic และ Traffy Fondue ด้วย Apache Airflow ทุก 15 นาที "
     "· ระดับรถติด (%) = เวลาเดินทางที่เพิ่มขึ้นเทียบกับตอนถนนโล่ง")

SOURCE_LABEL = {"tomtom_index": "TomTom Traffic Index", "longdo": "Longdo Traffic", "traffy": "Traffy Fondue"}
CATEGORY_LABEL = {"flood": "น้ำท่วม", "accident": "อุบัติเหตุ", "roadwork": "ก่อสร้าง/ซ่อมถนน", "closure": "ปิดถนน",
                  "traffic": "การจราจร", "road": "ถนนชำรุด", "other": "อื่น ๆ"}

total = query("SELECT COUNT(*) AS n FROM traffic_record")["n"].iloc[0]
if total == 0:
    st.info("ยังไม่มีข้อมูล เปิด Airflow (http://localhost:8080) แล้วกด ▶ ที่ DAG `bkk_traffic_pipeline` จากนั้นรีเฟรชหน้านี้")
    st.stop()

# ---------------- ตัวกรอง ----------------
with st.sidebar:
    st.header("ตัวกรอง")
    sources = st.multiselect("แหล่งข้อมูล", list(SOURCE_LABEL), default=list(SOURCE_LABEL),
                             format_func=SOURCE_LABEL.get)
    days = st.select_slider("เหตุการณ์ย้อนหลัง", [1, 3, 7, 14, 30], value=7, format_func=lambda d: f"{d} วัน")
    categories = st.multiselect("ประเภทเหตุการณ์", list(CATEGORY_LABEL), default=list(CATEGORY_LABEL),
                                format_func=CATEGORY_LABEL.get)
    search = st.text_input("ค้นหาชื่อเหตุการณ์/เขต", placeholder="เช่น น้ำท่วม, จตุจักร")

if not sources:
    st.warning("เลือกแหล่งข้อมูลอย่างน้อย 1 แหล่ง")
    st.stop()

congestion = query("""
    SELECT source_id, category, period, congestion_pct::float AS c, speed_kmh::float AS v, free_flow_kmh::float AS fv
    FROM traffic_record WHERE record_type = 'congestion'
""")
# หน้า TomTom มีข้อมูลหลายขอบเขต (เช่น metro/city และประเภทถนน) -> เลือกทีละขอบเขต ไม่ให้ช่วงเวลาซ้ำกัน
congestion["scope"] = congestion["source_id"].str.split(":").str[:2].str.join("/")
scopes = sorted(congestion["scope"].unique())
if scopes:
    with st.sidebar:
        scope = st.selectbox("ขอบเขตข้อมูล TomTom", scopes,
                             index=scopes.index("metro/all") if "metro/all" in scopes else 0)
    congestion = congestion[congestion["scope"] == scope]
records = query("""
    SELECT source, source_id, record_type, category, title, area, event_time, lat, lon, severity, dedup_key, last_seen
    FROM traffic_record
    WHERE record_type <> 'congestion' AND event_time >= NOW() - make_interval(days => %(d)s)
""", d=days)
records = records[records["source"].isin(sources) & records["category"].isin(categories)]
events = query("""
    SELECT dedup_key, title, category, sources, n_sources, n_records, first_time, max_severity, lat, lon
    FROM traffic_event WHERE first_time >= NOW() - make_interval(days => %(d)s)
""", d=days)
events = events[events["sources"].apply(lambda s: bool(set(s) & set(sources))) & events["category"].isin(categories)]
if search:
    records = records[records["title"].str.contains(search, case=False, na=False)
                      | records["area"].str.contains(search, case=False, na=False)]
    events = events[events["title"].str.contains(search, case=False, na=False)]


def pick(cat):
    row = congestion[congestion["category"] == cat]
    return row.iloc[0] if len(row) else None


# ---------------- KPI ----------------
base, pm = pick("base"), pick("pm")
k = st.columns(5)
k[0].metric("ข้อมูลสะสมทั้งหมด", f"{total:,}")
k[1].metric("รถติดเฉลี่ยทั้งปี", f"{base['c']:.0f}%" if base is not None else "-")
k[2].metric("ชั่วโมงเร่งด่วนเย็น", f"{pm['c']:.0f}%" if pm is not None else "-",
            pm["period"].replace("PM peak ", "") if pm is not None else None, delta_color="off")
k[3].metric(f"เหตุการณ์ {days} วัน", f"{len(events):,}")
k[4].metric("รายงานตรงกันหลายแหล่ง", f"{(events['n_sources'] > 1).sum():,}")

# ---------------- TomTom: ช่วงเวลาที่รถติด ----------------
if "tomtom_index" in sources and len(congestion):
    band(f"ระดับรถติดของกรุงเทพฯ ตามวันและเวลา จาก TomTom Traffic Index (ค่าเฉลี่ยทั้งปี · ขอบเขต {scope})")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("รถติดช่วงไหนของสัปดาห์")
        wh = congestion[congestion["category"] == "weekHour"].copy()
        if len(wh):
            wh["day"] = wh["period"].str.split(" ").str[0].str.split("-").str[1]
            wh["hour"] = wh["period"].str.split(" ").str[1].str[:2].astype(int)
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            th = dict(zip(order, ["จันทร์", "อังคาร", "พุธ", "พฤหัสฯ", "ศุกร์", "เสาร์", "อาทิตย์"]))
            pivot = wh.pivot_table(index="day", columns="hour", values="c", aggfunc="mean").reindex(index=order, columns=range(24))
            pivot.index = [th[d] for d in pivot.index]
            fig = px.imshow(pivot, color_continuous_scale="RdYlGn_r", aspect="auto",
                            labels={"x": "ชั่วโมง", "y": "", "color": "รถติด %"})
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("แนวโน้มรายเดือน")
        mo = congestion[congestion["category"] == "monthly"].sort_values("period")
        fig = px.line(mo, x="period", y="c", markers=True, labels={"period": "เดือน", "c": "รถติด %"})
        fig.update_traces(line_color=SOURCE_COLOR["tomtom_index"])
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ---------------- เหตุการณ์: แผนที่ + ประเภท ----------------
band(f"เหตุการณ์และเรื่องร้องเรียนด้านการจราจรในกรุงเทพฯ {days} วันล่าสุด จาก Longdo Traffic และ Traffy Fondue")
left, right = st.columns([3, 2])
with left:
    st.subheader("แผนที่เหตุการณ์ (ตัดซ้ำข้ามแหล่งแล้ว)")
    if len(events):
        m = events.copy()
        m["ประเภท"] = m["category"].map(CATEGORY_LABEL).fillna(m["category"])
        m["แหล่ง"] = m["sources"].apply(lambda s: ", ".join(SOURCE_LABEL.get(x, x) for x in s))
        fig = px.scatter_mapbox(m, lat="lat", lon="lon", color="ประเภท", size=m["n_sources"] * 4, size_max=14,
                                hover_name="title", hover_data={"แหล่ง": True, "lat": False, "lon": False},
                                color_discrete_map={CATEGORY_LABEL[k]: v for k, v in CATEGORY_COLOR.items()},
                                mapbox_style="carto-positron", zoom=10, center={"lat": 13.75, "lon": 100.56})
        fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ไม่มีเหตุการณ์ตามตัวกรองที่เลือก")
with right:
    st.subheader("จำนวนตามประเภทและแหล่ง")
    if len(records):
        cnt = records.groupby(["category", "source"]).size().reset_index(name="n")
        cnt["ประเภท"] = cnt["category"].map(CATEGORY_LABEL).fillna(cnt["category"])
        cnt["แหล่ง"] = cnt["source"].map(SOURCE_LABEL)
        fig = px.bar(cnt, x="n", y="ประเภท", color="แหล่ง", orientation="h",
                     color_discrete_map={SOURCE_LABEL[k]: v for k, v in SOURCE_COLOR.items()},
                     labels={"n": "จำนวน", "ประเภท": ""})
        fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ---------------- ตาราง ----------------
band("ตารางข้อมูล: เหตุการณ์หลังตัดรายการซ้ำข้ามแหล่ง, ข้อมูลรวมทุกแหล่ง และระดับรถติดจาก TomTom")
t1, t2, t3 = st.tabs(["เหตุการณ์ (ตัดซ้ำแล้ว)", "ข้อมูลรวมทุกแหล่ง", "ระดับรถติด TomTom"])
with t1:
    show = events.sort_values("first_time", ascending=False).copy()
    show["ประเภท"] = show["category"].map(CATEGORY_LABEL).fillna(show["category"])
    show["sources"] = show["sources"].apply(lambda s: ", ".join(SOURCE_LABEL.get(x, x) for x in s))
    show["first_time"] = pd.to_datetime(show["first_time"], utc=True).dt.tz_convert("Asia/Bangkok")
    st.dataframe(show[["first_time", "title", "ประเภท", "sources", "n_records"]], hide_index=True,
                 use_container_width=True,
                 column_config={"first_time": "เวลา", "title": "เหตุการณ์", "sources": "แหล่งที่รายงาน",
                                "n_records": "จำนวนรายการที่รวม"})
with t2:
    show = records.sort_values("event_time", ascending=False).copy()
    show["source"] = show["source"].map(SOURCE_LABEL)
    show["event_time"] = pd.to_datetime(show["event_time"], utc=True).dt.tz_convert("Asia/Bangkok")
    st.dataframe(show[["event_time", "source", "category", "title", "area", "source_id"]], hide_index=True,
                 use_container_width=True)
with t3:
    st.dataframe(congestion.drop(columns=["source_id"]).sort_values(["category", "period"]), hide_index=True,
                 use_container_width=True,
                 column_config={"category": "ประเภท", "period": "ช่วงเวลา", "c": "รถติด %",
                                "v": "ความเร็ว (กม./ชม.)", "fv": "ความเร็วตอนถนนโล่ง"})

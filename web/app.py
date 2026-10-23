from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from db import query
from theme import (BORDER, CHART_CONFIG, CATEGORY_COLOR, CYAN, GREEN, HEAT_SCALE, SOURCE_COLOR, TEXT2, alert_panel, apply_theme,
                   band, hero)

st.set_page_config(page_title="Bangkok Traffic", page_icon="⚡", layout="wide")
apply_theme()

SOURCE_LABEL = {"tomtom_index": "TomTom Traffic Index", "longdo": "Longdo Traffic", "traffy": "Traffy Fondue"}
CATEGORY_LABEL = {"traffic": "การจราจรติดขัด", "accident": "อุบัติเหตุ", "closure": "ปิดถนน",
                  "roadwork": "ก่อสร้าง/ซ่อมถนน", "flood": "น้ำท่วมผิวจราจร", "road": "ผิวถนนชำรุด", "other": "อื่น ๆ"}
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัสฯ", "ศุกร์", "เสาร์", "อาทิตย์"]

total = query("SELECT COUNT(*) AS n FROM traffic_record")["n"].iloc[0]
if total == 0:
    st.info("ยังไม่มีข้อมูล เปิด Airflow (http://localhost:8080) แล้วกด ▶ ที่ DAG `bkk_traffic_pipeline` จากนั้นรีเฟรชหน้านี้")
    st.stop()

# ---------------- ข้อมูลความหนาแน่น (TomTom) ----------------
congestion = query("""
    SELECT source_id, category, period, congestion_pct::float AS c, speed_kmh::float AS v, free_flow_kmh::float AS fv
    FROM traffic_record WHERE record_type = 'congestion'
""")
# หน้า TomTom มีข้อมูลหลายขอบเขต (เช่น metro/city และประเภทถนน) -> เลือกทีละขอบเขต ไม่ให้ช่วงเวลาซ้ำกัน
congestion["scope"] = congestion["source_id"].str.split(":").str[:2].str.join("/")
scopes = sorted(congestion["scope"].unique())

# ---------------- ตัวกรอง ----------------
now = datetime.now(timezone(timedelta(hours=7)))
with st.sidebar:
    st.header("ความหนาแน่น")
    scope = st.selectbox("ขอบเขตข้อมูล TomTom", scopes or ["-"],
                         index=scopes.index("metro/all") if "metro/all" in scopes else 0)
    day = st.selectbox("วันที่ต้องการดู", range(7), index=now.weekday(), format_func=lambda i: DAYS_TH[i])
    st.header("เหตุการณ์ที่ส่งผลต่อการจราจร")
    sources = st.multiselect("แหล่งข้อมูล", ["longdo", "traffy"], default=["longdo", "traffy"],
                             format_func=SOURCE_LABEL.get)
    days = st.select_slider("ย้อนหลัง", [1, 3, 7, 14, 30], value=7, format_func=lambda d: f"{d} วัน")
    categories = st.multiselect("ประเภท", list(CATEGORY_LABEL), default=list(CATEGORY_LABEL),
                                format_func=CATEGORY_LABEL.get)
    search = st.text_input("ค้นหาชื่อเหตุการณ์/เขต", placeholder="เช่น อุบัติเหตุ, จตุจักร")

congestion = congestion[congestion["scope"] == scope]
wh = congestion[congestion["category"] == "weekHour"].copy()
if len(wh):
    wh["day"] = wh["period"].str.split(" ").str[0].str.split("-").str[1]
    wh["hour"] = wh["period"].str.split(" ").str[1].str[:2].astype(int)


def pick(cat):
    row = congestion[congestion["category"] == cat]
    return row.iloc[0] if len(row) else None


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

# ---------------- ส่วนหัว ----------------
last = query("SELECT MAX(last_seen) AS t FROM traffic_record")["t"].iloc[0]
last_txt = pd.to_datetime(last, utc=True).tz_convert("Asia/Bangkok").strftime("%d/%m %H:%M") if last is not None else "-"
hero("Bangkok Traffic Density", "ความหนาแน่นการจราจรกรุงเทพฯ",
     "ระดับรถติด (%) = เวลาเดินทางที่เพิ่มขึ้นเมื่อเทียบกับตอนถนนโล่ง จาก TomTom Traffic Index (web scraping) "
     "พร้อมเหตุการณ์ที่ส่งผลต่อการจราจรจาก Longdo Traffic และ Traffy Fondue · อัปเดตด้วย Apache Airflow ทุก 15 นาที",
     live=f"อัปเดตล่าสุด {last_txt}")

# ---------------- KPI (3 ช่อง) ----------------
base = pick("base")
now_row = wh[(wh["day"] == DAYS_EN[now.weekday()]) & (wh["hour"] == now.hour)] if len(wh) else wh
worst = wh.loc[wh["c"].idxmax()] if len(wh) else None
k = st.columns(3)
k[0].metric(f"รถติดตอนนี้ · {DAYS_TH[now.weekday()]} {now:%H}:00",
            f"{now_row['c'].iloc[0]:.0f}%" if len(now_row) else "-",
            (f"ความเร็ว {now_row['v'].iloc[0]:.0f} กม./ชม."
             + (f" · เฉลี่ยทั้งปี {base['c']:.0f}%" if base is not None else "")) if len(now_row) else None,
            delta_color="off")
k[1].metric("ชั่วโมงที่ติดที่สุดของสัปดาห์", f"{worst['c']:.0f}%" if worst is not None else "-",
            f"{DAYS_TH[DAYS_EN.index(worst['day'])]} {worst['hour']:02d}:00 · ความเร็ว {worst['v']:.0f} กม./ชม."
            if worst is not None else None, delta_color="off")
k[2].metric(f"เหตุการณ์กระทบการจราจร · {days} วัน", f"{len(events):,}",
            f"รายงานตรงกันหลายแหล่ง {(events['n_sources'] > 1).sum():,} · ข้อมูลสะสม {total:,} รายการ",
            delta_color="off")

# ---------------- กราฟหลัก (8) + แผงแจ้งเตือน (4) ----------------
band(f"ค่าเฉลี่ยทั้งปีจาก TomTom Traffic Index · ขอบเขต {scope}", "ความหนาแน่นตามวันและเวลา")
left, right = st.columns([2, 1])
with left:
    if len(wh):
        pivot = wh.pivot_table(index="day", columns="hour", values="c", aggfunc="mean").reindex(index=DAYS_EN,
                                                                                               columns=range(24))
        pivot.index = DAYS_TH
        fig = px.imshow(pivot, color_continuous_scale=HEAT_SCALE, aspect="auto",
                        labels={"x": "ชั่วโมง", "y": "", "color": "รถติด %"})
        fig.update_traces(xgap=2, ygap=2, hovertemplate="%{y} %{x}:00<br>รถติด %{z:.0f}%<extra></extra>")
        fig.update_layout(height=400, margin=dict(l=8, r=8, t=16, b=8), xaxis=dict(dtick=2, showgrid=False),
                          yaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.info("ยังไม่มีข้อมูลจาก TomTom")
with right:
    latest = events.sort_values("first_time", ascending=False).head(6)
    items = []
    for _, e in latest.iterrows():
        t = pd.to_datetime(e["first_time"], utc=True).tz_convert("Asia/Bangkok")
        src = " + ".join(SOURCE_LABEL.get(x, x).split()[0] for x in e["sources"])
        items.append((e["category"], e["title"], CATEGORY_LABEL.get(e["category"], e["category"]),
                      f"{t:%d/%m %H:%M} · {src}"))
    alert_panel("⚠ เหตุการณ์ล่าสุด", items, f"{len(events)} รายการ")

# ---------------- ความหนาแน่นรายชั่วโมง (area) + รายเดือน ----------------
band("ระดับรถติดเทียบกับความเร็วจริงและความเร็วตอนถนนโล่ง", f"วัน{DAYS_TH[day]}: ความหนาแน่นรายชั่วโมง")
left, right = st.columns([2, 1])
with left:
    d = wh[wh["day"] == DAYS_EN[day]].sort_values("hour")
    if len(d):
        fig = go.Figure()
        fig.add_scatter(x=d["hour"], y=d["c"], name="รถติด %", mode="lines", line=dict(color=CYAN, width=3,
                        shape="spline"), fill="tozeroy", fillcolor="rgba(0,229,255,0.14)", yaxis="y")
        fig.add_scatter(x=d["hour"], y=d["v"], name="ความเร็วจริง", mode="lines",
                        line=dict(color=GREEN, width=2, shape="spline"), yaxis="y2")
        fig.add_scatter(x=d["hour"], y=d["fv"], name="ความเร็วตอนถนนโล่ง", mode="lines",
                        line=dict(color=TEXT2, width=1.5, dash="dot"), yaxis="y2")
        fig.update_layout(height=340, margin=dict(l=8, r=8, t=16, b=8), hovermode="x unified",
                          legend=dict(orientation="h", y=1.12, x=0),
                          xaxis=dict(title="ชั่วโมง", dtick=2, showgrid=False), yaxis=dict(title="รถติด %"),
                          yaxis2=dict(title="กม./ชม.", overlaying="y", side="right", showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
with right:
    mo = congestion[congestion["category"] == "monthly"].sort_values("period")
    if len(mo):
        fig = go.Figure(go.Scatter(x=mo["period"], y=mo["c"], mode="lines+markers", fill="tozeroy",
                                   line=dict(color=CYAN, width=2), fillcolor="rgba(0,229,255,0.10)",
                                   marker=dict(size=6, color=CYAN), hovertemplate="%{x}<br>%{y:.0f}%<extra></extra>"))
        fig.update_layout(height=340, margin=dict(l=8, r=8, t=40, b=8), showlegend=False,
                          title=dict(text="เฉลี่ยรายเดือน (%)", font=dict(size=14, color=TEXT2), x=0.02),
                          xaxis=dict(showgrid=False, tickangle=-45))
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

# ---------------- แผนที่ (8) + ประเภท (4) ----------------
band(f"{days} วันล่าสุด · Longdo Traffic + Traffy Fondue ตัดรายการซ้ำข้ามแหล่งแล้ว", "เหตุการณ์ที่ส่งผลต่อการจราจร")
left, right = st.columns([2, 1])
with left:
    if len(events):
        m = events.copy()
        m["ประเภท"] = m["category"].map(CATEGORY_LABEL).fillna(m["category"])
        m["แหล่ง"] = m["sources"].apply(lambda s: ", ".join(SOURCE_LABEL.get(x, x) for x in s))
        m["_size"] = m["n_sources"] * 4
        fig = px.scatter_mapbox(m, lat="lat", lon="lon", color="ประเภท", size="_size", size_max=14,
                                hover_name="title",
                                hover_data={"แหล่ง": True, "ประเภท": True, "_size": False, "lat": False, "lon": False},
                                color_discrete_map={CATEGORY_LABEL[k]: v for k, v in CATEGORY_COLOR.items()},
                                zoom=10.5, center={"lat": 13.75, "lon": 100.55}, opacity=0.9)
        # ระบุแหล่งภาพแผนที่เอง ไม่พึ่งสไตล์สำเร็จรูป และไม่ใช้ธีมของ Streamlit กับกราฟนี้ ไม่ให้ถูกเปลี่ยนเป็น CARTO
        fig.update_layout(height=440, margin=dict(l=0, r=0, t=0, b=0), mapbox_style="white-bg",
                          legend=dict(bgcolor="rgba(30,30,30,0.85)", x=0.01, y=0.99),
                          mapbox_layers=[{"below": "traces", "sourcetype": "raster", "opacity": 0.75,
                                          "sourceattribution": "© OpenStreetMap contributors",
                                          "source": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]}])
        st.plotly_chart(fig, use_container_width=True, theme=None, config=CHART_CONFIG)
    else:
        st.info("ไม่มีเหตุการณ์ตามตัวกรองที่เลือก")
with right:
    if len(records):
        cnt = records.groupby(["category", "source"]).size().reset_index(name="n")
        cnt["ประเภท"] = cnt["category"].map(CATEGORY_LABEL).fillna(cnt["category"])
        cnt["แหล่ง"] = cnt["source"].map(SOURCE_LABEL)
        fig = px.bar(cnt, x="n", y="ประเภท", color="แหล่ง", orientation="h",
                     color_discrete_map={SOURCE_LABEL[k]: v for k, v in SOURCE_COLOR.items()},
                     labels={"n": "จำนวน", "ประเภท": ""})
        fig.update_layout(height=440, margin=dict(l=8, r=8, t=40, b=8), bargap=0.35,
                          title=dict(text="จำนวนตามประเภทและแหล่ง", font=dict(size=14, color=TEXT2), x=0.02),
                          legend=dict(orientation="h", y=-0.12, title=None), yaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

# ---------------- ตาราง ----------------
band("ข้อมูลดิบจากทุกแหล่งและผลหลังรวม/ตัดรายการซ้ำ", "ตารางข้อมูล")
t1, t2, t3 = st.tabs(["ความหนาแน่น TomTom", "เหตุการณ์ (ตัดซ้ำข้ามแหล่งแล้ว)", "ข้อมูลรวมทุกแหล่ง"])
with t1:
    st.dataframe(congestion.drop(columns=["source_id"]).sort_values(["category", "period"]), hide_index=True,
                 use_container_width=True,
                 column_config={"category": "ประเภท", "period": "ช่วงเวลา", "c": "รถติด %",
                                "v": "ความเร็ว (กม./ชม.)", "fv": "ความเร็วตอนถนนโล่ง", "scope": "ขอบเขต"})
with t2:
    show = events.sort_values("first_time", ascending=False).copy()
    show["ประเภท"] = show["category"].map(CATEGORY_LABEL).fillna(show["category"])
    show["sources"] = show["sources"].apply(lambda s: ", ".join(SOURCE_LABEL.get(x, x) for x in s))
    show["first_time"] = pd.to_datetime(show["first_time"], utc=True).dt.tz_convert("Asia/Bangkok")
    st.dataframe(show[["first_time", "title", "ประเภท", "sources", "n_records"]], hide_index=True,
                 use_container_width=True,
                 column_config={"first_time": "เวลา", "title": "เหตุการณ์", "sources": "แหล่งที่รายงาน",
                                "n_records": "จำนวนรายการที่รวม"})
with t3:
    show = records.sort_values("event_time", ascending=False).copy()
    show["source"] = show["source"].map(SOURCE_LABEL)
    show["event_time"] = pd.to_datetime(show["event_time"], utc=True).dt.tz_convert("Asia/Bangkok")
    st.dataframe(show[["event_time", "source", "category", "title", "area", "source_id"]], hide_index=True,
                 use_container_width=True)

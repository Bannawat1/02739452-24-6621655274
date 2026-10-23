import pandas as pd
import plotly.express as px
import streamlit as st

from db import query
from theme import CHART_CONFIG, SOURCE_COLOR, apply_theme, band, hero

st.set_page_config(page_title="Pipeline Status", page_icon="🛠️", layout="wide")
apply_theme()
hero("Pipeline monitor", "สถานะ Pipeline", "ผลการรัน DAG bkk_traffic_pipeline แต่ละรอบ สถานะของแต่ละแหล่งข้อมูล และผลตรวจคุณภาพข้อมูล")

runs = query("""
    SELECT run_id, observed_at, started_at, finished_at, source_status, n_raw, n_valid, n_rejected,
           quality_passed, quality_reason, branch, status
    FROM pipeline_run ORDER BY observed_at DESC, finished_at DESC LIMIT 200
""")
if runs.empty:
    st.info("ยังไม่มีรอบที่รันเสร็จ")
    st.stop()

for c in ("observed_at", "started_at", "finished_at"):
    runs[c] = pd.to_datetime(runs[c], utc=True).dt.tz_convert("Asia/Bangkok")

ICON = {"SUCCESS": "🟢", "PARTIAL": "🟡", "QUALITY_FAILED": "🔴"}
STATE_ICON = {"success": "✅", "failed": "❌", "skipped": "⏭️", "upstream_failed": "❌"}

last = runs.iloc[0]
c = st.columns(4)
c[0].metric(f"รอบล่าสุด · {last['observed_at']:%d/%m}", last["observed_at"].strftime("%H:%M"))
c[1].metric(f"สถานะ {ICON.get(last['status'], '')}", last["status"].replace("QUALITY_FAILED", "QC FAILED"))
c[2].metric("แถวที่ผ่าน / เสีย", f"{last['n_valid']} / {last['n_rejected']}")
c[3].metric("อัตราสำเร็จ (ทุกรอบ)", f"{(runs['status'] != 'QUALITY_FAILED').mean():.0%}")

st.subheader("แหล่งข้อมูลในรอบล่าสุด")
cols = st.columns(len(last["source_status"]))
for col, (name, s) in zip(cols, last["source_status"].items()):
    col.metric(f"{STATE_ICON.get(s['state'], '❔')} {name} ({s.get('kind', '')})",
               f"{s.get('rows', 0)} แถว", s["state"], delta_color="off")

band(f"{last['quality_reason']} → branch: {last['branch']}", "ผลตรวจคุณภาพรอบล่าสุด")
st.subheader("ประวัติการรัน")
hist = []
for _, r in runs.iterrows():
    row = {"เวลา": r["observed_at"].strftime("%d/%m %H:%M"), "สถานะ": f"{ICON.get(r['status'], '')} {r['status']}",
           "branch": r["branch"], "ผ่าน": r["n_valid"], "เสีย": r["n_rejected"],
           "ใช้เวลา (วิ)": round((r["finished_at"] - r["started_at"]).total_seconds(), 1)
           if pd.notna(r["started_at"]) else None}
    for name, s in r["source_status"].items():
        row[name] = f"{STATE_ICON.get(s['state'], '❔')} {s.get('rows', 0)}"
    row["เหตุผล"] = r["quality_reason"]
    hist.append(row)
st.dataframe(pd.DataFrame(hist), hide_index=True, use_container_width=True)

st.subheader("จำนวนแถวต่อแหล่งในแต่ละรอบ")
long = [{"เวลา": r["observed_at"], "แหล่ง": n, "แถว": s.get("rows", 0)}
        for _, r in runs.iterrows() for n, s in r["source_status"].items()]
fig = px.bar(pd.DataFrame(long), x="เวลา", y="แถว", color="แหล่ง", barmode="stack", color_discrete_map=SOURCE_COLOR)
fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

st.subheader("ปัญหาคุณภาพข้อมูลล่าสุด")
issues = query("""
    SELECT created_at, source, source_id, problem FROM quality_issue ORDER BY created_at DESC LIMIT 200
""")
if issues.empty:
    st.success("ไม่พบแถวที่ไม่ผ่านการตรวจ")
else:
    st.dataframe(issues, hide_index=True, use_container_width=True)

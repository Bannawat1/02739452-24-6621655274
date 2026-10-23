"""ธีมของ dashboard ตาม DESIGN-sap.md

- พื้นขาว, chrome เทา #f5f6f7, แถบ #eaecee, สีเน้นน้ำเงิน #0057d2 สีเดียว
- ไม่มีเงา, มุมโค้ง 8px (control/การ์ด) และ 12px (กรอบกราฟ), แบ่ง section ด้วยแถบสีพื้น
- ฟอนต์: Inter (ละติน) + Noto Sans Thai (ไทย) แทน 72 Brand ซึ่งเป็นฟอนต์ลิขสิทธิ์ ใช้น้ำหนัก 350/400/500/700
"""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

PRIMARY, PRIMARY_DEEP, NAVY, SKY = "#0057d2", "#0040b0", "#022879", "#6bc0ff"
INK, INK_BODY, INK_LIST, INK_META, INK_NAV = "#000000", "#223548", "#354a5f", "#475e75", "#545454"
CHROME, BAND = "#f5f6f7", "#eaecee"
FONT = "Inter, 'Noto Sans Thai', sans-serif"

# สีของแต่ละแหล่ง: ใช้โทนน้ำเงินของแบรนด์
SOURCE_COLOR = {"tomtom_index": PRIMARY, "longdo": NAVY, "traffy": SKY}
# สีของประเภทเหตุการณ์ (สีตามความหมาย)
CATEGORY_COLOR = {"flood": "#1f77b4", "accident": "#d22828", "roadwork": "#f0781e", "closure": "#6e0f0f",
                  "traffic": "#e6b41e", "road": "#8c6d46", "other": INK_META}

_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@350..700&family=Noto+Sans+Thai:wght@350..700&display=swap" rel="stylesheet">
<style>
html, body, [class*="st-"], .stMarkdown, .stMetric, button, input, textarea, select {{
    font-family: {FONT} !important; letter-spacing: 0 !important;
}}
.stApp {{ background: #ffffff; }}
header[data-testid="stHeader"] {{ background: {CHROME}; height: 3.2rem; }}
.block-container {{ padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1360px; }}

/* sidebar = chrome เทาอ่อน, แถวเมนูที่เลือกใช้แถบน้ำเงิน */
section[data-testid="stSidebar"] {{ background: {CHROME}; border-right: 0; }}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; color: {INK_NAV}; font-size: 15px; font-weight: 400; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: #ffffff; color: {PRIMARY}; font-weight: 500; box-shadow: inset 3px 0 0 {PRIMARY};
}}

/* หัวเรื่อง */
h1, h2, h3 {{ color: {INK}; letter-spacing: 0 !important; }}
h3 {{ font-size: 20px !important; font-weight: 500 !important; padding-top: .4rem; }}

/* hero band: navy -> blue */
.hero {{
    background: linear-gradient(100deg, {NAVY} 0%, {PRIMARY_DEEP} 55%, {PRIMARY} 100%);
    color: #fff; padding: 32px 40px; margin: 0 0 24px 0;
}}
.hero .eyebrow {{ font-size: 14px; font-weight: 500; color: {SKY}; text-transform: uppercase; margin-bottom: 8px; }}
.hero h1 {{ color: #fff; font-size: 36px; font-weight: 500; line-height: 1.1; margin: 0; padding: 0; }}
.hero p {{ color: #fff; opacity: .88; font-size: 16px; font-weight: 350; margin: 12px 0 0 0; max-width: 900px; }}

/* KPI: การ์ดแบนบนพื้นเทา ไม่มีเงา มุม 8px */
[data-testid="stMetric"] {{ background: {CHROME}; border-radius: 8px; padding: 16px 20px; }}
[data-testid="stMetricLabel"] p {{ color: {INK_META}; font-size: 14px; font-weight: 400; white-space: normal; }}
[data-testid="stMetricLabel"] div {{ overflow: visible; }}
[data-testid="stMetricDelta"] div {{ white-space: normal; }}
[data-testid="stMetricValue"] {{ color: {INK}; font-size: 30px; font-weight: 700; }}

/* กรอบกราฟ 12px */
[data-testid="stPlotlyChart"] {{ border: 1px solid {BAND}; border-radius: 12px; padding: 8px; }}

/* ตาราง/แท็บ */
[data-testid="stDataFrame"] {{ border-radius: 8px; overflow: hidden; }}
.stTabs [data-baseweb="tab"] {{ font-size: 15px; color: {INK_NAV}; }}
.stTabs [aria-selected="true"] {{ color: {PRIMARY}; font-weight: 500; }}

/* ปุ่มและ control */
.stButton button, .stDownloadButton button {{ border-radius: 8px; box-shadow: none; }}
[data-baseweb="select"] > div, [data-baseweb="input"] {{ border-radius: 8px; }}
[data-baseweb="tag"] {{ background: {PRIMARY} !important; border-radius: 4px; }}

.meta {{ color: {INK_META}; font-size: 14px; }}
.band {{ background: {CHROME}; padding: 16px 20px; margin: 24px 0 8px 0; color: {INK_BODY}; font-size: 15px; }}
</style>
"""


def apply_theme():
    # markdown ของ Streamlit ตัดบล็อก HTML ที่บรรทัดว่าง จึงต้องลบบรรทัดว่างออกก่อน
    st.markdown("\n".join(line for line in _CSS.splitlines() if line.strip()), unsafe_allow_html=True)


def hero(eyebrow, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


def band(text):
    st.markdown(f'<div class="band">{text}</div>', unsafe_allow_html=True)


# template ของ plotly: พื้นขาว เส้นกริดเทาอ่อน ฟอนต์เดียวกับหน้าเว็บ
pio.templates["sap"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=INK_BODY, size=13),
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    colorway=[PRIMARY, NAVY, SKY, INK_META, PRIMARY_DEEP],
    xaxis=dict(gridcolor=BAND, linecolor=BAND, zerolinecolor=BAND, title_font=dict(color=INK_META)),
    yaxis=dict(gridcolor=BAND, linecolor=BAND, zerolinecolor=BAND, title_font=dict(color=INK_META)),
    legend=dict(title_font=dict(color=INK_META)),
    hoverlabel=dict(font_family=FONT),
))
pio.templates.default = "sap"

"""ธีมของ dashboard ตาม DESIGN.md "WattVision"

- โหมดมืด: พื้น #121212, การ์ด #1E1E1E มุม 16px ขอบ 1px #2C2C2E, padding 20px, ระยะห่างทวีคูณ 8px
- สีเน้นข้อมูล #00E5FF (ฟ้านีออน), แจ้งเตือน #FF453A (แดง), ปกติ/สด #32D74B (เขียว)
- ข้อความหลัก #FFFFFF, ข้อความรอง #98989D, เส้นกริด #2C2C2E
- ฟอนต์: Inter + IBM Plex Sans Thai (หัวข้อ/เนื้อหา), JetBrains Mono (ตัวเลข KPI)
"""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

BG, CARD, BORDER, HOVER = "#121212", "#1E1E1E", "#2C2C2E", "#252525"
CYAN, CYAN_DIM, GREEN, RED, AMBER = "#00E5FF", "#0097A7", "#32D74B", "#FF453A", "#FFD60A"
TEXT, TEXT2 = "#FFFFFF", "#98989D"
FONT = "Inter, 'IBM Plex Sans Thai', sans-serif"
MONO = "'JetBrains Mono', 'IBM Plex Sans Thai', monospace"

# ชื่อเดิมที่หน้าอื่นใช้อยู่
PRIMARY, SKY, INK_META = CYAN, GREEN, TEXT2

# สีของแต่ละแหล่ง
SOURCE_COLOR = {"tomtom_index": CYAN, "longdo": GREEN, "traffy": "#BF5AF2"}
# สีของประเภทเหตุการณ์ (สีตามความหมาย, อ่านได้บนพื้นมืด)
CATEGORY_COLOR = {"traffic": AMBER, "accident": RED, "closure": "#FF375F", "roadwork": "#FF9F0A",
                  "flood": "#0A84FF", "road": "#AC8E68", "other": TEXT2}
# ซ่อนแถบเครื่องมือของ plotly ไม่ให้ทับคำอธิบายกราฟ
CHART_CONFIG = {"displayModeBar": False}
# สเกลสีระดับรถติด: เขียว (โล่ง) -> เหลือง -> แดง (ติดหนัก)
HEAT_SCALE = [[0, "#1B3A2A"], [0.25, GREEN], [0.55, AMBER], [1, RED]]

_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="st-"], .stMarkdown, button, input, textarea, select, label {{
    font-family: {FONT} !important; letter-spacing: 0 !important;
}}
.stApp {{ background: {BG}; color: {TEXT}; }}
header[data-testid="stHeader"] {{ background: {BG}; }}
.block-container {{ padding-top: 3rem; padding-bottom: 3rem; max-width: 1440px; }}
p, li, span, label {{ font-size: 14px; }}
/* sidebar */
section[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] h2 {{ font-size: 13px !important; font-weight: 600 !important; color: {TEXT2};
    text-transform: uppercase; letter-spacing: .04em !important; margin-top: 16px; }}
[data-testid="stSidebarNav"] a {{ border-radius: 12px; }}
[data-testid="stSidebarNav"] a span {{ color: {TEXT2}; font-size: 15px; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {HOVER}; box-shadow: inset 3px 0 0 {CYAN}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {TEXT}; font-weight: 600; }}
/* หัวเรื่อง */
h1, h2, h3 {{ color: {TEXT}; letter-spacing: 0 !important; }}
h3 {{ font-size: 18px !important; font-weight: 600 !important; padding: 8px 0 0 0 !important; }}
/* ส่วนหัว */
.hero {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
    padding: 8px 0 24px 0; margin-bottom: 8px; border-bottom: 1px solid {BORDER}; }}
.hero .eyebrow {{ font-size: 12px; font-weight: 600; color: {CYAN}; text-transform: uppercase;
    letter-spacing: .08em !important; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }}
.hero h1 {{ color: {TEXT}; font-size: 28px; font-weight: 600; line-height: 1.25; margin: 0; padding: 0; }}
.hero p {{ color: {TEXT2}; font-size: 14px; margin: 8px 0 0 0; max-width: 860px; line-height: 1.6; }}
.live {{ display: inline-flex; align-items: center; gap: 8px; color: {GREEN}; font-size: 13px; font-weight: 600;
    background: rgba(50,215,75,.12); border: 1px solid rgba(50,215,75,.35); padding: 6px 12px; border-radius: 999px;
    white-space: nowrap; }}
.live::before {{ content: ""; width: 8px; height: 8px; border-radius: 50%; background: {GREEN};
    box-shadow: 0 0 8px {GREEN}; }}
/* KPI */
[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 20px; }}
[data-testid="stMetricLabel"] p {{ color: {TEXT2}; font-size: 13px; font-weight: 500; white-space: normal; }}
[data-testid="stMetricLabel"] div {{ overflow: visible; }}
[data-testid="stMetricValue"] {{ color: {CYAN}; font-family: {MONO} !important; font-size: 32px; font-weight: 700; }}
[data-testid="stMetricValue"] div {{ font-family: {MONO} !important; white-space: normal; overflow: visible;
    font-size: clamp(22px, 2.1vw, 32px); line-height: 1.2; }}
[data-testid="stMetricDelta"] div {{ white-space: normal; color: {TEXT2} !important; font-size: 13px; }}
[data-testid="stMetricDelta"] svg {{ display: none; }}
/* การ์ดกราฟ */
[data-testid="stPlotlyChart"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 12px; }}
/* ตาราง/แท็บ */
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 16px; overflow: hidden; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ color: {TEXT2}; }}
.stTabs [aria-selected="true"] {{ color: {CYAN}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {CYAN}; }}
/* control */
[data-baseweb="select"] > div, [data-baseweb="input"] {{ border-radius: 12px; background: {BG};
    border-color: {BORDER}; }}
[data-baseweb="tag"] {{ background: rgba(0,229,255,.14) !important; border-radius: 8px; }}
[data-baseweb="tag"] span {{ color: {CYAN} !important; }}
/* แถบหัวข้อของแต่ละส่วน */
.band {{ color: {TEXT2}; font-size: 13px; margin: 32px 0 8px 0; padding-left: 12px; border-left: 3px solid {CYAN}; }}
.band b {{ color: {TEXT}; font-size: 18px; font-weight: 600; display: block; margin-bottom: 2px; }}
/* แผงแจ้งเตือน */
.alerts {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 20px; height: 100%; }}
.alerts h4 {{ color: {TEXT}; font-size: 16px; font-weight: 600; margin: 0 0 16px 0; display: flex;
    justify-content: space-between; align-items: center; }}
.alerts h4 span {{ font-family: {MONO}; color: {RED}; font-size: 14px; }}
.alert {{ background: #3A1C1C; border-left: 4px solid {RED}; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }}
.alert.flood {{ background: #10263F; border-left-color: #0A84FF; }}
.alert.traffic, .alert.roadwork {{ background: #3A311A; border-left-color: {AMBER}; }}
.alert .t {{ color: {TEXT}; font-size: 14px; font-weight: 500; line-height: 1.4; }}
.alert .m {{ color: {TEXT2}; font-size: 12px; margin-top: 4px; }}
.alert .m b {{ color: {RED}; font-weight: 600; }}
.alert.flood .m b {{ color: #0A84FF; }}
.alert.traffic .m b, .alert.roadwork .m b {{ color: {AMBER}; }}
.meta {{ color: {TEXT2}; font-size: 13px; }}
</style>
"""


def apply_theme():
    # markdown ของ Streamlit ตัดบล็อก HTML ที่บรรทัดว่าง จึงต้องลบบรรทัดว่างออกก่อน
    st.markdown("\n".join(line for line in _CSS.splitlines() if line.strip()), unsafe_allow_html=True)


def hero(eyebrow, title, subtitle, live=None):
    badge = f'<div class="live">{live}</div>' if live else ""
    st.markdown(f'<div class="hero"><div><div class="eyebrow">⚡ {eyebrow}</div><h1>{title}</h1><p>{subtitle}</p>'
                f'</div>{badge}</div>', unsafe_allow_html=True)


def band(text, title=None):
    st.markdown(f'<div class="band">{f"<b>{title}</b>" if title else ""}{text}</div>', unsafe_allow_html=True)


def alert_panel(title, items, count_label=""):
    """items: [(category, title, meta_bold, meta_rest)]"""
    rows = "".join(f'<div class="alert {c}"><div class="t">{t}</div><div class="m"><b>{b}</b> · {m}</div></div>'
                   for c, t, b, m in items) or f'<div class="meta">ไม่มีเหตุการณ์ตามตัวกรอง</div>'
    st.markdown(f'<div class="alerts"><h4>{title}<span>{count_label}</span></h4>{rows}</div>', unsafe_allow_html=True)


# template ของ plotly: พื้นการ์ดมืด เส้นกริด #2C2C2E ฟอนต์เดียวกับหน้าเว็บ
pio.templates["watt"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=TEXT2, size=13),
    paper_bgcolor=CARD, plot_bgcolor=CARD,
    colorway=[CYAN, GREEN, "#BF5AF2", AMBER, RED],
    xaxis=dict(gridcolor=BORDER, linecolor=BORDER, zerolinecolor=BORDER, title_font=dict(color=TEXT2)),
    yaxis=dict(gridcolor=BORDER, linecolor=BORDER, zerolinecolor=BORDER, title_font=dict(color=TEXT2)),
    legend=dict(title_font=dict(color=TEXT2), font=dict(color=TEXT)),
    hoverlabel=dict(font_family=FONT, bgcolor=CARD, bordercolor=BORDER, font_color=TEXT),
    coloraxis=dict(colorbar=dict(tickfont=dict(color=TEXT2), title_font=dict(color=TEXT2))),
))
pio.templates.default = "watt"

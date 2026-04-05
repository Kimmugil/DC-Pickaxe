import os, json, math
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="DC-Pickaxe 관제탑", page_icon="⛏️", layout="wide")
KST = timezone(timedelta(hours=9))
COLORS = ["#FEE500","#7C6FF7","#50C8A8","#F4A844","#F47B7B","#60A5FA","#A78BFA","#34D399"]

# ── CSS (Soft Pastel Admin V2) ────────────────────────────────
st.markdown(
    "<style>"
    ".stApp,[data-testid='stAppViewContainer']>.main{background:#F5F6FA!important}"
    "[data-testid='stHeader']{background:transparent!important;box-shadow:none}"
    "[data-testid='stToolbar']{display:none}"
    ".block-container{padding:1.2rem 1.6rem!important;max-width:1300px}"
    "section[data-testid='stSidebar']{background:#FFFFFF!important;border-right:1px solid #EEEEF5!important}"
    "section[data-testid='stSidebar'] .block-container{padding:0!important;max-width:none!important}"
    "section[data-testid='stSidebar'] .stButton>button{"
    "background:transparent!important;border:none!important;box-shadow:none!important;"
    "text-align:left!important;color:#6B7280!important;font-weight:500!important;"
    "padding:10px 20px!important;border-radius:12px!important;font-size:14px!important;"
    "width:100%;transition:all .15s!important}"
    "section[data-testid='stSidebar'] .stButton>button:hover{background:#F0EEFF!important;color:#7C6FF7!important}"
    ".pastel-card{background:#FFFFFF;border-radius:24px;padding:24px;box-shadow:0 10px 40px rgba(139,126,255,.07);margin-bottom:14px}"
    ".mcard{background:#FFFFFF;border-radius:24px;padding:22px 16px 18px;text-align:center;box-shadow:0 10px 40px rgba(139,126,255,.07)}"
    ".mval{font-size:26px;font-weight:800;color:#1E1E1E;line-height:1.2}"
    ".mlbl{font-size:10px;color:#9CA3AF;font-weight:700;text-transform:uppercase;letter-spacing:.7px;margin-top:4px}"
    ".ctitle{font-size:14px;font-weight:700;color:#374151;margin:0 0 16px}"
    ".badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;white-space:nowrap}"
    ".bs{background:#DCFCE7;color:#15803D}.bi{background:#DBEAFE;color:#1D4ED8}"
    ".be{background:#FEE2E2;color:#B91C1C}.bn{background:#F3F4F6;color:#6B7280}"
    ".stl{font-size:15px;font-weight:700;color:#1E1E1E;padding-left:12px;border-left:4px solid #7C6FF7;margin:18px 0 10px}"
    ".th{font-size:10px;color:#9CA3AF;font-weight:700;text-transform:uppercase;letter-spacing:.6px;padding:0 6px;margin-bottom:4px}"
    ".rc{background:#FFFFFF;border-radius:12px;padding:11px 14px;box-shadow:0 4px 16px rgba(139,126,255,.06);font-size:13px;color:#374151}"
    ".stLinkButton>a{background:#F0EEFF!important;color:#7C6FF7!important;border:1.5px solid #D4CFFE!important;border-radius:10px!important;font-size:12px!important;font-weight:600!important}"
    ".stLinkButton>a:hover{background:#E5E0FF!important}"
    "[data-testid='stExpander']{background:#FFFFFF!important;border-radius:18px!important;border:1px solid #EEEEF5!important}"
    "[data-testid='stDataFrame']{border-radius:16px;overflow:hidden}"
    "</style>",
    unsafe_allow_html=True
)


# ── SVG Chart Helpers ─────────────────────────────────────────

def _pts(values, w, h, pad=16):
    """Normalize values to SVG coordinate list"""
    vmin, vmax = min(values), max(values)
    if vmax == vmin: vmax = vmin + 1
    n = len(values)
    return [
        (pad + (i / max(n - 1, 1)) * (w - 2 * pad),
         pad + (1 - (v - vmin) / (vmax - vmin)) * (h - 2 * pad))
        for i, v in enumerate(values)
    ]

def svg_line_area(values: list, width=560, height=130,
                  line_color="#7C6FF7", fill_color="#7C6FF7") -> str:
    """Smooth cubic-bezier line + semi-transparent fill area"""
    if len(values) < 2:
        return ""
    pts = _pts(values, width, height)
    pad = 16
    # build smooth cubic path
    path = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        cx = (x0 + x1) / 2
        path += f" C {cx:.1f},{y0:.1f} {cx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    fill = (path
            + f" L {pts[-1][0]:.1f},{height - pad:.1f}"
            + f" L {pts[0][0]:.1f},{height - pad:.1f} Z")
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>"
        f"<defs><linearGradient id='lg' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0%' stop-color='{fill_color}' stop-opacity='.18'/>"
        f"<stop offset='100%' stop-color='{fill_color}' stop-opacity='.01'/>"
        f"</linearGradient></defs>"
        f"<path d='{fill}' fill='url(#lg)'/>"
        f"<path d='{path}' fill='none' stroke='{line_color}' stroke-width='2.5'"
        f" stroke-linecap='round' stroke-linejoin='round'/>"
        f"</svg>"
    )

def svg_bar_h(data: dict, width=480, height=200) -> str:
    """Horizontal bar chart — good for gallery name labels"""
    if not data:
        return ""
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    n = len(items)
    vmax = max(v for _, v in items) or 1
    row_h = (height - 10) / n
    bar_area = width - 100  # leave left margin for labels
    bars = ""
    for i, (label, val) in enumerate(items):
        y = i * row_h + row_h * 0.15
        bh = row_h * 0.55
        bw = (val / vmax) * bar_area
        color = COLORS[i % len(COLORS)]
        short = (label[:7] + "…") if len(label) > 8 else label
        bars += (
            f"<text x='90' y='{y + bh * 0.78:.1f}' text-anchor='end'"
            f" font-size='12' fill='#6B7280' font-weight='500'>{short}</text>"
            f"<rect x='96' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}'"
            f" rx='6' fill='{color}'/>"
            f"<text x='{96 + bw + 5:.1f}' y='{y + bh * 0.78:.1f}'"
            f" font-size='11' fill='#9CA3AF'>{val:,}</text>"
        )
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{bars}</svg>"
    )

def svg_bar_daily(dates: list, values: list, width=580, height=160) -> str:
    """Vertical bar chart for daily post counts"""
    if not values:
        return ""
    n = len(values)
    vmax = max(values) or 1
    pad_l, pad_r, pad_top, pad_bot = 8, 8, 20, 28
    cw = (width - pad_l - pad_r) / n
    bar_w = max(cw * 0.65, 2)
    chart_h = height - pad_top - pad_bot
    bars = ""
    for i, (d, v) in enumerate(zip(dates, values)):
        x = pad_l + i * cw + (cw - bar_w) / 2
        bh = (v / vmax) * chart_h
        y = pad_top + chart_h - bh
        bars += (
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{bh:.1f}'"
            f" rx='3' fill='#FEE500'/>"
        )
        # x-axis label every ~7 items
        if n <= 14 or i % max(n // 6, 1) == 0:
            label = str(d)[5:] if isinstance(d, str) and len(str(d)) >= 7 else str(d)
            bars += (
                f"<text x='{x + bar_w / 2:.1f}' y='{height - 6:.1f}'"
                f" text-anchor='middle' font-size='9' fill='#9CA3AF'>{label}</text>"
            )
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{bars}</svg>"
    )

def svg_donut(data: dict, size=170) -> str:
    """Donut chart with legend"""
    if not data or sum(data.values()) == 0:
        return ""
    total = sum(data.values())
    color_map = {"수집성공": "#22C55E", "새글없음": "#60A5FA",
                 "에러": "#F87171", "미실행": "#E5E7EB"}
    cx = cy = size / 2
    ro, ri = size * 0.40, size * 0.24
    angle = -90.0
    slices = ""
    for label, val in data.items():
        if val == 0:
            continue
        sweep = (val / total) * 360
        end = angle + sweep
        sr, er = math.radians(angle), math.radians(end)
        ox1, oy1 = cx + ro * math.cos(sr), cy + ro * math.sin(sr)
        ox2, oy2 = cx + ro * math.cos(er), cy + ro * math.sin(er)
        ix1, iy1 = cx + ri * math.cos(er), cy + ri * math.sin(er)
        ix2, iy2 = cx + ri * math.cos(sr), cy + ri * math.sin(sr)
        la = 1 if sweep > 180 else 0
        c = color_map.get(label, "#9CA3AF")
        d = (f"M {ox1:.1f} {oy1:.1f} "
             f"A {ro:.1f} {ro:.1f} 0 {la} 1 {ox2:.1f} {oy2:.1f} "
             f"L {ix1:.1f} {iy1:.1f} "
             f"A {ri:.1f} {ri:.1f} 0 {la} 0 {ix2:.1f} {iy2:.1f} Z")
        slices += f"<path d='{d}' fill='{c}'/>"
        angle = end
    # center text
    slices += (
        f"<text x='{cx:.0f}' y='{cy - 6:.0f}' text-anchor='middle'"
        f" font-size='18' font-weight='800' fill='#1E1E1E'>{total}</text>"
        f"<text x='{cx:.0f}' y='{cy + 12:.0f}' text-anchor='middle'"
        f" font-size='10' fill='#9CA3AF'>갤러리</text>"
    )
    return (
        f"<svg width='{size}' height='{size}' viewBox='0 0 {size} {size}'"
        f" xmlns='http://www.w3.org/2000/svg'>{slices}</svg>"
    )


# ── Data Loading ──────────────────────────────────────────────

@st.cache_resource
def get_client():
    j = os.environ.get('GCP_CREDENTIALS')
    if not j: return None
    d = json.loads(j)
    sc = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
    return gspread.authorize(Credentials.from_service_account_info(d, scopes=sc))

@st.cache_data(ttl=60)
def load_master():
    c = get_client()
    if not c: return None
    url = os.environ.get('MASTER_SHEET_URL')
    if not url: return None
    recs = c.open_by_url(url).sheet1.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in recs])

@st.cache_data(ttl=300)
def get_count(url: str) -> int:
    c = get_client()
    if not c: return -1
    try:
        return sum(1 for v in c.open_by_url(url).sheet1.col_values(1) if str(v).isdigit())
    except: return -1

@st.cache_data(ttl=300)
def load_gallery(url: str) -> pd.DataFrame:
    c = get_client()
    if not c: return pd.DataFrame()
    try:
        res = c.open_by_url(url).sheet1.batch_get(['A:B', 'D:I'])
        ab = res[0] if res else []
        di = res[1] if len(res) > 1 else []
        if not ab: return pd.DataFrame()
        rows = []
        for i in range(max(len(ab), len(di))):
            a = list(ab[i]) if i < len(ab) else []
            d = list(di[i]) if i < len(di) else []
            while len(a) < 2: a.append('')
            while len(d) < 6: d.append('')
            if not str(a[0]).isdigit(): continue
            rows.append({'글번호': a[0], '제목': a[1], '작성자': d[0],
                         '날짜': d[1], '링크': d[2],
                         '댓글수': d[3] or '0', '조회수': d[4] or '0', '추천수': d[5] or '0'})
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows)
        df['날짜_dt']   = pd.to_datetime(df['날짜'], errors='coerce')
        df['날짜_date'] = df['날짜_dt'].dt.date
        for col in ['댓글수','조회수','추천수']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df.sort_values('날짜_dt').reset_index(drop=True)
    except: return pd.DataFrame()


# ── Helpers ───────────────────────────────────────────────────

def time_ago(s):
    try:
        t = datetime.strptime(str(s).strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        m = int((datetime.now(KST) - t).total_seconds() / 60)
        if m < 1: return "방금 전"
        if m < 60: return f"{m}분 전"
        if m < 1440: return f"{m//60}시간 전"
        return f"{m//1440}일 전"
    except: return str(s) or "-"

def bdg(msg):
    m = str(msg).strip()
    if not m:             return '<span class="badge bn">⚪ 미실행</span>'
    if "에러"    in m:    return f'<span class="badge be">❌ {m}</span>'
    if "새 글 없음" in m: return '<span class="badge bi">✅ 새 글 없음</span>'
    if "개 수집" in m:    return f'<span class="badge bs">🟢 {m}</span>'
    return f'<span class="badge bn">{m}</span>'

def find_col(df, *kws):
    for kw in kws:
        for c in df.columns:
            if kw in c: return c
    return None

def rf_btn(key="rf"):
    if st.button("🔄 새로고침", use_container_width=True, key=key):
        st.cache_data.clear(); st.rerun()


# ── Sidebar ───────────────────────────────────────────────────

def render_sidebar(df, nc, ic, counts):
    with st.sidebar:
        st.markdown(
            "<div style='padding:26px 20px 16px'>"
            "<p style='font-size:18px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ DC-Pickaxe</p>"
            "<p style='font-size:11px;color:#9CA3AF;margin:3px 0 0'>갤러리 수집 관제 시스템</p>"
            "</div>"
            "<div style='height:1px;background:#F0F0F8;margin:0 16px'></div>"
            "<div style='padding:16px 20px 4px'>"
            "<p style='font-size:10px;font-weight:700;color:#C4C4D4;letter-spacing:1px;text-transform:uppercase;margin:0'>MENU</p>"
            "</div>",
            unsafe_allow_html=True
        )
        if st.button("🏠  메인 대시보드", use_container_width=True, key="sb_main"):
            st.session_state.page = 'main'; st.rerun()
        if df is not None and not df.empty:
            st.markdown(
                "<div style='padding:16px 20px 4px'>"
                "<p style='font-size:10px;font-weight:700;color:#C4C4D4;letter-spacing:1px;text-transform:uppercase;margin:0'>갤러리</p>"
                "</div>",
                unsafe_allow_html=True
            )
            for i, (_, row) in enumerate(df.iterrows()):
                gn  = str(row.get(nc, ''))
                gid = str(row.get(ic, '')) if ic else str(i)
                cnt = counts.get(gn, -1)
                lbl = f"📊  {gn}" + (f"  ({cnt:,})" if cnt >= 0 else "")
                if st.button(lbl, use_container_width=True, key=f"sb_{gid}"):
                    st.session_state.page = gid; st.rerun()
        st.markdown(
            "<div style='position:fixed;bottom:0;padding:14px 20px;"
            "border-top:1px solid #F0F0F8;background:white;width:inherit'>"
            "<p style='font-size:11px;color:#9CA3AF;margin:0'>DC-Pickaxe v2.2</p>"
            "<p style='font-size:11px;color:#9CA3AF;margin:2px 0 0'>PM : 김무길</p>"
            "</div>",
            unsafe_allow_html=True
        )


# ── Main Page ─────────────────────────────────────────────────

def page_main(df, nc, ic, uc, rc, lc, counts):
    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    hc, bc = st.columns([9, 1])
    with hc:
        st.markdown(
            "<div style='background:linear-gradient(90deg,#FEE500,#FFD000);border-radius:24px;"
            "padding:20px 28px;box-shadow:0 10px 40px rgba(254,229,0,.3);"
            "display:flex;align-items:center;justify-content:space-between;margin-bottom:20px'>"
            "<div>"
            "<p style='font-size:22px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ DC-Pickaxe 관제탑</p>"
            "<p style='font-size:12px;color:#555;margin:4px 0 0'>디시인사이드 갤러리 자동 수집 모니터링</p>"
            "</div>"
            f"<div style='text-align:right;font-size:12px;color:#444'>"
            f"🕐 현재 시각 (KST)<br><strong>{now}</strong></div>"
            "</div>",
            unsafe_allow_html=True
        )
    with bc:
        st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
        rf_btn("rf_main")

    total = len(df)
    errs  = sum(1 for v in df[lc] if "에러" in str(v)) if lc else 0
    tp    = sum(v for v in counts.values() if v >= 0)
    lr    = str(df[rc].iloc[0]) if rc else ""

    m1, m2, m3, m4 = st.columns(4)
    for col, top_c, icon, val, lbl in [
        (m1, "#7C6FF7", "🗂️", f"{total}개",              "등록 갤러리"),
        (m2, "#50C8A8", "📄", f"{tp:,}건",                "총 수집 게시글"),
        (m3, "#F4A844", "✅", f"{total-errs}/{total}",    "정상 갤러리"),
        (m4, "#F47B7B", "🕐", time_ago(lr),               "마지막 실행"),
    ]:
        with col:
            st.markdown(
                f"<div class='mcard' style='border-top:4px solid {top_c}'>"
                f"<div style='font-size:22px;margin-bottom:8px'>{icon}</div>"
                f"<div class='mval'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 차트 2종
    ch1, ch2 = st.columns([3, 2])
    with ch1:
        bar_svg = svg_bar_h({k: max(v,0) for k,v in counts.items()}) if counts else ""
        st.markdown(
            "<div class='pastel-card'>"
            "<p class='ctitle'>갤러리별 수집 게시글 수</p>"
            f"{bar_svg}"
            "</div>",
            unsafe_allow_html=True
        )
    with ch2:
        if lc:
            sm = {'수집성공':0,'새글없음':0,'에러':0,'미실행':0}
            for v in df[lc]:
                s = str(v)
                if '개 수집' in s: sm['수집성공'] += 1
                elif '새 글 없음' in s: sm['새글없음'] += 1
                elif '에러' in s: sm['에러'] += 1
                else: sm['미실행'] += 1
            donut = svg_donut({k: v for k,v in sm.items() if v > 0})
            color_map = {"수집성공":"#22C55E","새글없음":"#60A5FA","에러":"#F87171","미실행":"#E5E7EB"}
            legend = "".join(
                f"<span style='display:inline-flex;align-items:center;gap:5px;margin:3px 8px 3px 0;"
                f"font-size:12px;color:#6B7280'>"
                f"<span style='width:10px;height:10px;border-radius:50%;background:{color_map.get(k,\"#999\")}'></span>"
                f"{k} {v}</span>"
                for k, v in sm.items() if v > 0
            )
            st.markdown(
                "<div class='pastel-card'>"
                "<p class='ctitle'>수집 상태 분포</p>"
                f"<div style='display:flex;align-items:center;justify-content:center'>{donut}</div>"
                f"<div style='text-align:center;margin-top:10px'>{legend}</div>"
                "</div>",
                unsafe_allow_html=True
            )

    # 갤러리 현황 테이블
    st.markdown("<p class='stl'>📋 갤러리별 수집 현황</p>", unsafe_allow_html=True)
    hcols = st.columns([3, 2.5, 2, 2, 1.6])
    for c, t in zip(hcols, ["갤러리","수집 상태","총 게시글","마지막 실행","바로가기"]):
        c.markdown(f"<p class='th'>{t}</p>", unsafe_allow_html=True)

    for i, (_, row) in enumerate(df.iterrows()):
        color = COLORS[i % len(COLORS)]
        gn = str(row.get(nc,''));  gi = str(row.get(ic,'')) if ic else ''
        rm = str(row.get(lc,'')) if lc else '';  lr2 = str(row.get(rc,'')) if rc else ''
        su = str(row.get(uc,'')) if uc else '';  cnt = counts.get(gn,-1)
        c1,c2,c3,c4,c5 = st.columns([3,2.5,2,2,1.6])
        with c1:
            st.markdown(
                f"<div class='rc' style='border-left:5px solid {color};border-radius:0 12px 12px 0'>"
                f"<div style='font-weight:700;font-size:14px;color:#1E1E1E'>{gn}</div>"
                f"<div style='font-size:11px;color:#9CA3AF'>{gi}</div></div>",
                unsafe_allow_html=True
            )
        with c2: st.markdown(f"<div class='rc'>{bdg(rm)}</div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='rc' style='font-weight:700'>📄 {f'{cnt:,}건' if cnt>=0 else '집계 중'}</div>", unsafe_allow_html=True)
        with c4: st.markdown(f"<div class='rc' style='color:#6B7280'>🕐 {time_ago(lr2)}</div>", unsafe_allow_html=True)
        with c5:
            if su.startswith('http'): st.link_button("열기 →", su, use_container_width=True)
        st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

    st.markdown("<p style='text-align:right;font-size:11px;color:#9CA3AF'>💡 총 게시글 수는 5분 주기 갱신</p>", unsafe_allow_html=True)
    st.markdown("---")
    with st.expander("📚 온보딩 스크래퍼 실행 가이드"):
        st.markdown(
            "온보딩 스크래퍼는 **반드시 로컬 PC에서 실행**해야 합니다."
            " 어제부터 역방향으로 수집하며 **Ctrl+C로 언제든 중단**해도 저장된 데이터는 보존됩니다.\n\n"
            "1. `git clone [깃허브 주소]`\n"
            "2. `.env` 파일에 `GCP_CREDENTIALS` / `MASTER_SHEET_URL` 입력\n"
            "3. `pip install -r requirements.txt`\n"
            "4. `python onboarding_scraper.py` → 갤러리 선택"
        )
    st.markdown("<p style='text-align:right;color:#9CA3AF;font-size:11px'>시스템 총괄 PM : 김무길 | DC-Pickaxe v2.2</p>", unsafe_allow_html=True)


# ── Gallery Detail Page ───────────────────────────────────────

def page_gallery(row, nc, ic, uc, rc, lc):
    gn = str(row.get(nc,''));  gi = str(row.get(ic,'')) if ic else ''
    su = str(row.get(uc,'')) if uc else '';  lr = str(row.get(rc,'')) if rc else ''
    rm = str(row.get(lc,'')) if lc else ''

    hc, bc = st.columns([9, 1])
    with hc:
        st.markdown(
            "<div class='pastel-card' style='border-left:5px solid #7C6FF7;border-radius:0 24px 24px 0;margin-bottom:18px'>"
            f"<p style='font-size:20px;font-weight:900;color:#1E1E1E;margin:0'>📊 {gn}</p>"
            f"<p style='font-size:12px;color:#9CA3AF;margin:5px 0 0'>"
            f"ID: {gi} &nbsp;|&nbsp; 최근 수집: {time_ago(lr)} &nbsp;|&nbsp; {bdg(rm)}</p>"
            "</div>",
            unsafe_allow_html=True
        )
    with bc:
        st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
        rf_btn("rf_gall")

    with st.spinner("갤러리 데이터 로딩 중... (최초 1회만 소요)"):
        gdf = load_gallery(su)

    if gdf.empty:
        st.info("수집된 게시글이 없습니다. 온보딩 스크래퍼를 실행해주세요.")
        return

    total = len(gdf)
    vd = gdf['날짜_date'].dropna()
    dmin = vd.min() if len(vd) else None
    dmax = vd.max() if len(vd) else None
    days = max((dmax - dmin).days + 1, 1) if dmin and dmax else 1
    avg  = round(total / days, 1)

    m1,m2,m3,m4 = st.columns(4)
    for col, top_c, icon, val, lbl in [
        (m1,"#7C6FF7","📄",f"{total:,}건","총 수집 게시글"),
        (m2,"#50C8A8","📅",str(dmin) if dmin else "-","최초 수집 날짜"),
        (m3,"#F4A844","🗓️",str(dmax) if dmax else "-","최근 수집 날짜"),
        (m4,"#F47B7B","📈",f"{avg}건/일","일평균 게시글"),
    ]:
        with col:
            st.markdown(
                f"<div class='mcard' style='border-top:4px solid {top_c}'>"
                f"<div style='font-size:20px;margin-bottom:6px'>{icon}</div>"
                f"<div class='mval' style='font-size:20px'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div></div>",
                unsafe_allow_html=True
            )
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 일별 게시글 수 (최근 60일)
    daily = (gdf.groupby('날짜_date').size().reset_index(name='수')
             .sort_values('날짜_date').tail(60))
    dates_list = [str(d) for d in daily['날짜_date'].tolist()]
    vals_list  = daily['수'].tolist()
    bar_svg = svg_bar_daily(dates_list, vals_list)
    st.markdown(
        "<div class='pastel-card'>"
        "<p class='ctitle'>📅 일별 게시글 수 (최근 60일)</p>"
        f"{bar_svg}"
        "</div>",
        unsafe_allow_html=True
    )

    # 누적 추이
    all_daily = (gdf.groupby('날짜_date').size().reset_index(name='수').sort_values('날짜_date'))
    all_daily['누적'] = all_daily['수'].cumsum()
    cumul_vals = all_daily['누적'].tolist()
    line_svg = svg_line_area(cumul_vals, line_color="#7C6FF7", fill_color="#7C6FF7")
    # x-axis date labels (first, middle, last)
    dl = all_daily['날짜_date'].tolist()
    date_label = ""
    if dl:
        idxs = [0, len(dl)//2, len(dl)-1]
        for idx in idxs:
            pct = (idx / max(len(dl)-1, 1)) * 100
            date_label += (
                f"<span style='position:absolute;left:{pct:.0f}%;transform:translateX(-50%);"
                f"font-size:10px;color:#9CA3AF'>{str(dl[idx])[5:]}</span>"
            )
    st.markdown(
        "<div class='pastel-card'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>"
        "<p class='ctitle' style='margin:0'>📈 누적 게시글 추이</p>"
        f"<span style='font-size:22px;font-weight:800;color:#7C6FF7'>{total:,}건</span>"
        "</div>"
        f"{line_svg}"
        f"<div style='position:relative;height:18px;margin-top:4px'>{date_label}</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # 최근 게시글 목록
    st.markdown("<div class='pastel-card'>", unsafe_allow_html=True)
    tc, bc2 = st.columns([6, 2])
    with tc: st.markdown("<p class='ctitle'>📝 최근 수집 게시글 (최신 50건)</p>", unsafe_allow_html=True)
    with bc2:
        if su.startswith('http'): st.link_button("📊 전체 시트 열기 →", su, use_container_width=True)
    recent = gdf.sort_values('날짜_dt', ascending=False).head(50)
    st.dataframe(
        recent[['글번호','제목','작성자','날짜','댓글수','조회수','추천수']].reset_index(drop=True),
        use_container_width=True, hide_index=True,
        column_config={
            '글번호':  st.column_config.TextColumn('글번호',  width='small'),
            '제목':    st.column_config.TextColumn('제목',    width='large'),
            '작성자':  st.column_config.TextColumn('작성자',  width='small'),
            '날짜':    st.column_config.TextColumn('날짜',    width='medium'),
            '댓글수':  st.column_config.NumberColumn('💬 댓글', width='small'),
            '조회수':  st.column_config.NumberColumn('👁️ 조회', width='small'),
            '추천수':  st.column_config.NumberColumn('👍 추천', width='small'),
        }
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ── App Entry ─────────────────────────────────────────────────

if 'page' not in st.session_state:
    st.session_state.page = 'main'

df = load_master()
if df is None or df.empty:
    st.error("❌ GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")
    st.stop()

nc = find_col(df,'명') or df.columns[0]
ic = find_col(df,'ID','id') or (df.columns[1] if len(df.columns)>1 else None)
uc = find_col(df,'URL','url','시트')
rc = find_col(df,'시각','시간') or (df.columns[3] if len(df.columns)>3 else None)
lc = find_col(df,'개수','결과') or (df.columns[4] if len(df.columns)>4 else None)

counts: dict = {}
if uc:
    for _, row in df.iterrows():
        url = str(row.get(uc,''))
        gn  = str(row.get(nc,''))
        if url.startswith('http'):
            counts[gn] = get_count(url)

render_sidebar(df, nc, ic, counts)

if st.session_state.page == 'main':
    page_main(df, nc, ic, uc, rc, lc, counts)
else:
    match = df[df[ic] == st.session_state.page] if ic and ic in df.columns else pd.DataFrame()
    if not match.empty:
        page_gallery(match.iloc[0], nc, ic, uc, rc, lc)
    else:
        st.session_state.page = 'main'; st.rerun()

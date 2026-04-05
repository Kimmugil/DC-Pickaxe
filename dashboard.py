import os
import json
import pandas as pd
import altair as alt
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="DC-Pickaxe 관제탑", page_icon="⛏️", layout="wide")

CARD_COLORS = ["#FEE500", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899"]

st.markdown("""
<style>
    /* ── 전체 배경 (화이트 모드 고정) ── */
    .stApp, [data-testid="stAppViewContainer"] > .main {
        background: #f8faff !important;
    }
    [data-testid="stHeader"]  { background: transparent !important; box-shadow: none; }
    [data-testid="stToolbar"] { display: none; }
    .block-container { padding-top: 1.4rem !important; max-width: 1200px; }

    /* ── 헤더 배너 ── */
    .header-banner {
        background: linear-gradient(90deg, #FEE500 0%, #FFD000 100%);
        border-radius: 20px;
        padding: 20px 30px;
        margin-bottom: 22px;
        box-shadow: 0 6px 24px rgba(254,229,0,0.35);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header-title { font-size: 24px; font-weight: 900; color: #111; margin: 0; }
    .header-sub   { font-size: 13px; color: #555; margin-top: 4px; }
    .header-time  { text-align: right; font-size: 13px; color: #444; line-height: 1.7; }

    /* ── 메트릭 카드 ── */
    .metric-card {
        background: #fff;
        border-radius: 16px;
        padding: 20px 16px 16px;
        text-align: center;
        box-shadow: 0 2px 16px rgba(0,0,0,0.07);
    }
    .metric-icon  { font-size: 24px; margin-bottom: 6px; }
    .metric-value { font-size: 26px; font-weight: 800; color: #1f2937; line-height: 1.2; }
    .metric-label { font-size: 11px; color: #9ca3af; font-weight: 700;
                    letter-spacing: 0.7px; text-transform: uppercase; margin-top: 5px; }

    /* ── 섹션 타이틀 ── */
    .section-title {
        font-size: 16px; font-weight: 700; color: #374151;
        margin: 22px 0 10px;
        border-left: 4px solid #FEE500;
        padding-left: 10px;
    }

    /* ── 차트 컨테이너 ── */
    .chart-card {
        background: #fff;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.06);
    }
    .chart-title {
        font-size: 14px; font-weight: 700; color: #374151; margin-bottom: 12px;
    }

    /* ── 테이블 헤더 ── */
    .table-header {
        font-size: 11px; color: #9ca3af; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.6px;
        padding: 0 6px; margin-bottom: 5px;
    }

    /* ── 갤러리 이름 블록 ── */
    .gall-name-block {
        background: #fff;
        border-radius: 10px;
        padding: 10px 14px;
        box-shadow: 0 1px 8px rgba(0,0,0,0.05);
    }
    .gall-name { font-weight: 700; font-size: 14px; color: #1f2937; }
    .gall-id   { font-size: 11px; color: #9ca3af; margin-top: 1px; }

    /* ── 메타 블록 ── */
    .meta-block {
        background: #fff;
        border-radius: 10px;
        padding: 10px 12px;
        box-shadow: 0 1px 8px rgba(0,0,0,0.05);
        font-size: 13px;
        color: #374151;
        display: flex;
        align-items: center;
        height: 100%;
    }

    /* ── 상태 배지 ── */
    .badge { display:inline-block; padding:4px 12px; border-radius:20px;
             font-size:12px; font-weight:700; white-space:nowrap; }
    .badge-success { background:#dcfce7; color:#15803d; }
    .badge-info    { background:#dbeafe; color:#1d4ed8; }
    .badge-error   { background:#fee2e2; color:#b91c1c; }
    .badge-neutral { background:#f3f4f6; color:#6b7280; }

    /* ── 버튼 스타일 ── */
    .stLinkButton > a {
        background: #f0f7ff !important; color: #2563eb !important;
        border: 1.5px solid #bfdbfe !important; border-radius: 10px !important;
        font-size: 12px !important; font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stLinkButton > a:hover {
        background: #dbeafe !important; border-color: #60a5fa !important;
    }
    .stButton > button {
        background: #fff !important; border: 1.5px solid #e5e7eb !important;
        border-radius: 10px !important; color: #374151 !important;
        font-weight: 600 !important; font-size: 13px !important;
    }

    /* ── expander ── */
    [data-testid="stExpander"] {
        background: #fff !important;
        border-radius: 14px !important;
        border: 1px solid #e9ecef !important;
        box-shadow: 0 1px 8px rgba(0,0,0,0.04) !important;
    }

    /* ── 행 간격 ── */
    .row-gap { margin-bottom: 8px; }

    /* ── Altair 차트 배경 흰색 ── */
    .vega-embed { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────

@st.cache_resource
def get_sheets_client():
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        return None
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def load_master_data():
    client = get_sheets_client()
    if not client:
        return None
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        return None
    sheet = client.open_by_url(master_url).sheet1
    records = sheet.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in records])


@st.cache_data(ttl=300)
def get_post_count(sheet_url: str) -> int:
    client = get_sheets_client()
    if not client:
        return -1
    try:
        vals = client.open_by_url(sheet_url).sheet1.col_values(1)
        return sum(1 for v in vals if str(v).isdigit())
    except Exception:
        return -1


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

def get_time_ago(time_str: str) -> str:
    try:
        KST = timezone(timedelta(hours=9))
        t = datetime.strptime(str(time_str).strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        m = int((datetime.now(KST) - t).total_seconds() / 60)
        if m < 1:    return "방금 전"
        if m < 60:   return f"{m}분 전"
        if m < 1440: return f"{m // 60}시간 전"
        return f"{m // 1440}일 전"
    except Exception:
        return str(time_str) or "없음"


def badge(msg: str) -> str:
    msg = str(msg).strip()
    if not msg:               return '<span class="badge badge-neutral">⚪ 미실행</span>'
    if "에러"    in msg:       return f'<span class="badge badge-error">❌ {msg}</span>'
    if "새 글 없음" in msg:    return '<span class="badge badge-info">✅ 새 글 없음</span>'
    if "개 수집" in msg:       return f'<span class="badge badge-success">🟢 {msg}</span>'
    return f'<span class="badge badge-neutral">{msg}</span>'


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────

KST = timezone(timedelta(hours=9))
now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

hcol, bcol = st.columns([8, 1])
with hcol:
    st.markdown(f"""
    <div class="header-banner">
      <div>
        <p class="header-title">⛏️ DC-Pickaxe 관제탑</p>
        <p class="header-sub">디시인사이드 갤러리 자동 수집 모니터링 시스템</p>
      </div>
      <div class="header-time">🕐 현재 시각 (KST)<br><strong>{now_str}</strong></div>
    </div>
    """, unsafe_allow_html=True)
with bcol:
    st.markdown("<div style='padding-top:10px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────
# 데이터 로드 & 컬럼 탐지
# ─────────────────────────────────────────────

df = load_master_data()
if df is None or df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다. GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")
    st.stop()

name_col        = next((c for c in df.columns if '명' in c), df.columns[0])
id_col          = next((c for c in df.columns if 'ID' in c or 'id' in c), df.columns[1] if len(df.columns) > 1 else None)
sheet_url_col   = next((c for c in df.columns if 'URL' in c or '시트' in c), None)
last_run_col    = next((c for c in df.columns if '시각' in c or '시간' in c), df.columns[3] if len(df.columns) > 3 else None)
last_result_col = next((c for c in df.columns if '개수' in c or '결과' in c), df.columns[4] if len(df.columns) > 4 else None)

# 게시글 수 집계
post_counts: dict[str, int] = {}
if sheet_url_col:
    with st.spinner("📊 갤러리별 게시글 수 집계 중... (최초 1회만 소요)"):
        for _, row in df.iterrows():
            url   = str(row.get(sheet_url_col, ''))
            gname = str(row.get(name_col, ''))
            if url.startswith('http'):
                post_counts[gname] = get_post_count(url)

total_posts    = sum(v for v in post_counts.values() if v >= 0)
total_galleries = len(df)
error_count    = sum(1 for v in df[last_result_col] if "에러" in str(v)) if last_result_col else 0
normal_count   = total_galleries - error_count
latest_run     = str(df[last_run_col].iloc[0]) if last_run_col else ""

# ─────────────────────────────────────────────
# 요약 메트릭 4종
# ─────────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)
for col, icon, value, label, color in [
    (m1, "🗂️",  f"{total_galleries}개",                   "등록 갤러리",    "#3b82f6"),
    (m2, "📄",  f"{total_posts:,}건",                      "총 수집 게시글", "#10b981"),
    (m3, "✅",  f"{normal_count} / {total_galleries}",     "정상 갤러리",    "#f59e0b"),
    (m4, "🕐",  get_time_ago(latest_run),                  "마지막 실행",    "#8b5cf6"),
]:
    with col:
        st.markdown(f"""
        <div class="metric-card" style="border-top:4px solid {color};">
          <div class="metric-icon">{icon}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 시각화 차트 2종
# ─────────────────────────────────────────────

st.markdown('<div class="section-title">📊 수집 현황 시각화</div>', unsafe_allow_html=True)

chart_left, chart_right = st.columns([3, 2])

with chart_left:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<p class="chart-title">갤러리별 총 수집 게시글 수</p>', unsafe_allow_html=True)
    if post_counts:
        bar_df = pd.DataFrame([
            {'갤러리': k, '게시글 수': max(v, 0)} for k, v in post_counts.items()
        ]).sort_values('게시글 수', ascending=False)

        bar_chart = (
            alt.Chart(bar_df)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            .encode(
                x=alt.X('갤러리:N', sort=None, title='',
                         axis=alt.Axis(labelAngle=0, labelFontSize=12)),
                y=alt.Y('게시글 수:Q', title='게시글 수',
                         axis=alt.Axis(format=',d', labelFontSize=11)),
                color=alt.Color('갤러리:N',
                                scale=alt.Scale(scheme='tableau10'),
                                legend=None),
                tooltip=[
                    alt.Tooltip('갤러리:N',   title='갤러리'),
                    alt.Tooltip('게시글 수:Q', title='수집량', format=','),
                ]
            )
            .properties(height=230)
            .configure_view(strokeWidth=0)
            .configure_axis(grid=True, gridColor='#f0f0f0')
        )
        st.altair_chart(bar_chart, use_container_width=True)
    else:
        st.info("게시글 수 데이터를 불러오는 중입니다.")
    st.markdown('</div>', unsafe_allow_html=True)

with chart_right:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<p class="chart-title">갤러리 수집 상태 분포</p>', unsafe_allow_html=True)
    if last_result_col:
        status_map = {'🟢 수집 성공': 0, '✅ 새 글 없음': 0, '❌ 에러': 0, '⚪ 미실행': 0}
        for v in df[last_result_col]:
            s = str(v)
            if '개 수집'    in s: status_map['🟢 수집 성공'] += 1
            elif '새 글 없음' in s: status_map['✅ 새 글 없음'] += 1
            elif '에러'     in s: status_map['❌ 에러'] += 1
            else:                 status_map['⚪ 미실행']    += 1

        pie_df = pd.DataFrame([
            {'상태': k, '수': v} for k, v in status_map.items() if v > 0
        ])
        color_map = {
            '🟢 수집 성공': '#22c55e',
            '✅ 새 글 없음': '#3b82f6',
            '❌ 에러':       '#ef4444',
            '⚪ 미실행':    '#d1d5db',
        }
        pie_chart = (
            alt.Chart(pie_df)
            .mark_arc(innerRadius=55, outerRadius=95)
            .encode(
                theta=alt.Theta('수:Q'),
                color=alt.Color(
                    '상태:N',
                    scale=alt.Scale(
                        domain=list(color_map.keys()),
                        range=list(color_map.values())
                    ),
                    legend=alt.Legend(orient='bottom', labelFontSize=12)
                ),
                tooltip=['상태:N', '수:Q']
            )
            .properties(height=230)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(pie_chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 갤러리별 현황 테이블
# ─────────────────────────────────────────────

st.markdown('<div class="section-title">📋 갤러리별 수집 현황</div>', unsafe_allow_html=True)

# 컬럼 헤더
hc = st.columns([3.2, 2.5, 2, 2, 1.6])
for col, label in zip(hc, ["갤러리", "수집 상태", "총 게시글", "마지막 실행", "바로가기"]):
    col.markdown(f"<p class='table-header'>{label}</p>", unsafe_allow_html=True)

for idx, row in df.iterrows():
    color      = CARD_COLORS[idx % len(CARD_COLORS)]
    gname      = str(row.get(name_col, ''))
    gid        = str(row.get(id_col, '')) if id_col else ''
    result_msg = str(row.get(last_result_col, '')) if last_result_col else ''
    last_run   = str(row.get(last_run_col, '')) if last_run_col else ''
    sheet_url  = str(row.get(sheet_url_col, '')) if sheet_url_col else ''
    count      = post_counts.get(gname, -1)
    count_str  = f"{count:,}건" if count >= 0 else "집계 중"

    c1, c2, c3, c4, c5 = st.columns([3.2, 2.5, 2, 2, 1.6])

    with c1:
        st.markdown(f"""
        <div class="gall-name-block" style="border-left:5px solid {color};">
          <div class="gall-name">{gname}</div>
          <div class="gall-id">{gid}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="meta-block">{badge(result_msg)}</div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="meta-block" style="font-weight:700;">📄 {count_str}</div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="meta-block" style="color:#6b7280;">🕐 {get_time_ago(last_run)}</div>', unsafe_allow_html=True)
    with c5:
        if sheet_url.startswith('http'):
            st.link_button("열기 →", sheet_url, use_container_width=True)

    st.markdown("<div class='row-gap'></div>", unsafe_allow_html=True)

st.markdown(
    "<p style='text-align:right; font-size:11px; color:#9ca3af; margin-top:2px;'>"
    "💡 총 게시글 수는 5분 주기로 갱신됩니다. 봇은 약 15분 간격으로 실행됩니다.</p>",
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────
# 온보딩 가이드
# ─────────────────────────────────────────────

st.markdown("---")
with st.expander("📚 온보딩(과거 데이터) 스크래퍼 실행 가이드"):
    st.markdown(
        "디시인사이드 봇 차단 정책으로 인해 **온보딩은 반드시 로컬 PC에서 실행**해야 합니다.\n\n"
        "온보딩 스크래퍼는 **어제부터 역방향**으로 수집하며, "
        "**Ctrl+C로 중단해도 저장된 데이터는 보존**됩니다."
    )
    st.markdown("""
1. `git clone [퍼블릭 깃허브 주소]` 로 코드를 로컬에 다운로드합니다.
2. 폴더에 `.env` 파일 생성 후 아래 내용 입력:
   ```
   GCP_CREDENTIALS={...서비스계정 JSON 전체...}
   MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/...
   ```
3. `pip install -r requirements.txt` 로 패키지 설치
4. `python onboarding_scraper.py` 실행 → 갤러리 번호 선택 → 자동 시작
    """)

st.markdown(
    "<p style='text-align:right; color:#9ca3af; font-size:12px; padding:6px 0;'>"
    "시스템 총괄 PM : 김무길 &nbsp;|&nbsp; DC-Pickaxe v2.1</p>",
    unsafe_allow_html=True
)

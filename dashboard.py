import os
import json
import pandas as pd
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
    /* 배경 */
    [data-testid="stAppViewContainer"] > .main {
        background: linear-gradient(140deg, #f0f4ff 0%, #faf5ff 50%, #f0fdf4 100%);
        min-height: 100vh;
    }
    [data-testid="stHeader"] { background: transparent !important; box-shadow: none; }
    [data-testid="stToolbar"] { display: none; }
    .block-container { padding-top: 1.5rem !important; }

    /* 헤더 배너 */
    .header-banner {
        background: linear-gradient(90deg, #FEE500 0%, #FFD000 100%);
        border-radius: 20px;
        padding: 22px 32px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(254,229,0,0.38);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header-title { font-size: 26px; font-weight: 900; color: #111; margin: 0; letter-spacing: -0.5px; }
    .header-sub   { font-size: 13px; color: #555; margin-top: 5px; }
    .header-time  { text-align: right; color: #444; font-size: 13px; line-height: 1.6; }

    /* 메트릭 카드 */
    .metric-card {
        background: white;
        border-radius: 18px;
        padding: 22px 16px 18px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.07);
        height: 100%;
    }
    .metric-icon  { font-size: 26px; margin-bottom: 8px; }
    .metric-value { font-size: 28px; font-weight: 800; color: #1f2937; line-height: 1.2; }
    .metric-label { font-size: 11px; color: #9ca3af; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 6px; }

    /* 섹션 타이틀 */
    .section-title {
        font-size: 17px; font-weight: 700; color: #374151;
        margin: 24px 0 10px; padding-left: 6px;
        border-left: 4px solid #FEE500; padding-left: 10px;
    }

    /* 갤러리 카드 행 헤더 */
    .table-header {
        font-size: 11px; color: #9ca3af; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.7px;
        padding: 0 6px; margin-bottom: 6px;
    }

    /* 갤러리 이름 블록 */
    .gall-name-block {
        border-radius: 10px;
        padding: 10px 14px;
        background: white;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        height: 100%;
    }
    .gall-name  { font-weight: 700; font-size: 15px; color: #1f2937; }
    .gall-id    { font-size: 12px; color: #9ca3af; margin-top: 2px; }

    /* 메타 블록 (상태·카운트·시간) */
    .meta-block {
        background: white;
        border-radius: 10px;
        padding: 10px 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        font-size: 14px;
        color: #374151;
        height: 100%;
        display: flex;
        align-items: center;
    }

    /* 상태 배지 */
    .badge { display:inline-block; padding:5px 13px; border-radius:20px; font-size:13px; font-weight:700; }
    .badge-success { background:#dcfce7; color:#15803d; }
    .badge-info    { background:#dbeafe; color:#1d4ed8; }
    .badge-error   { background:#fee2e2; color:#b91c1c; }
    .badge-neutral { background:#f3f4f6; color:#6b7280; }

    /* link_button 스타일 */
    .stLinkButton > a {
        background: #f0f7ff !important;
        color: #2563eb !important;
        border: 1.5px solid #bfdbfe !important;
        border-radius: 10px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 0 !important;
        transition: all 0.2s !important;
    }
    .stLinkButton > a:hover {
        background: #dbeafe !important;
        border-color: #60a5fa !important;
        box-shadow: 0 2px 8px rgba(59,130,246,0.2) !important;
    }

    /* 새로고침 버튼 */
    .stButton > button {
        background: white !important;
        border: 1.5px solid #e5e7eb !important;
        border-radius: 10px !important;
        color: #374151 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    .stButton > button:hover {
        border-color: #9ca3af !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }

    /* 구분선 */
    hr { border: none; border-top: 1px solid #e9ecef; margin: 24px 0; }

    /* expander */
    [data-testid="stExpander"] {
        background: white;
        border-radius: 14px !important;
        border: 1px solid #e9ecef !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }

    /* 행 간격 */
    .row-gap { margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 데이터 로드 함수들
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
    master_sheet = client.open_by_url(master_url).sheet1
    records = master_sheet.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in records])


@st.cache_data(ttl=300)
def get_post_count(sheet_url: str) -> int:
    """개별 갤러리 시트에서 수집된 게시글 수를 반환합니다. (5분 캐시)"""
    client = get_sheets_client()
    if not client:
        return -1
    try:
        sheet = client.open_by_url(sheet_url).sheet1
        vals = sheet.col_values(1)
        return sum(1 for v in vals if str(v).isdigit())
    except Exception:
        return -1


# ─────────────────────────────────────────────
# 헬퍼 함수들
# ─────────────────────────────────────────────

def get_time_ago(time_str: str) -> str:
    time_str = str(time_str).strip()
    if not time_str:
        return "없음"
    try:
        KST = timezone(timedelta(hours=9))
        last_run = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        minutes = int((datetime.now(KST) - last_run).total_seconds() / 60)
        if minutes < 1:   return "방금 전"
        if minutes < 60:  return f"{minutes}분 전"
        if minutes < 1440: return f"{minutes // 60}시간 전"
        return f"{minutes // 1440}일 전"
    except Exception:
        return time_str


def get_badge_html(result_msg: str) -> str:
    msg = str(result_msg).strip()
    if not msg:
        return '<span class="badge badge-neutral">⚪ 미실행</span>'
    if "에러" in msg:
        return f'<span class="badge badge-error">❌ {msg}</span>'
    if "새 글 없음" in msg:
        return '<span class="badge badge-info">✅ 새 글 없음</span>'
    if "개 수집" in msg:
        return f'<span class="badge badge-success">🟢 {msg}</span>'
    return f'<span class="badge badge-neutral">{msg}</span>'


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────

KST = timezone(timedelta(hours=9))
now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

header_col, btn_col = st.columns([8, 1])
with header_col:
    st.markdown(f"""
    <div class="header-banner">
        <div>
            <p class="header-title">⛏️ DC-Pickaxe 관제탑</p>
            <p class="header-sub">디시인사이드 갤러리 자동 수집 모니터링 시스템</p>
        </div>
        <div class="header-time">
            🕐 현재 시각 (KST)<br>
            <strong>{now_str}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
with btn_col:
    st.markdown("<div style='padding-top:8px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────

df = load_master_data()

if df is None or df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다. GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")
    st.stop()

# 컬럼명 자동 탐지
name_col       = next((c for c in df.columns if '명' in c), df.columns[0])
id_col         = next((c for c in df.columns if 'ID' in c or 'id' in c), df.columns[1] if len(df.columns) > 1 else None)
sheet_url_col  = next((c for c in df.columns if 'URL' in c or '시트' in c), None)
last_run_col   = next((c for c in df.columns if '시각' in c or '시간' in c), df.columns[3] if len(df.columns) > 3 else None)
last_result_col = next((c for c in df.columns if '개수' in c or '결과' in c), df.columns[4] if len(df.columns) > 4 else None)

# ─────────────────────────────────────────────
# 게시글 수 집계 (캐시 사용)
# ─────────────────────────────────────────────

post_counts: dict[str, int] = {}
if sheet_url_col:
    with st.spinner("📊 갤러리별 게시글 수 집계 중... (최초 1회만 소요)"):
        for _, row in df.iterrows():
            url = str(row.get(sheet_url_col, ''))
            gname = str(row.get(name_col, ''))
            if url.startswith('http'):
                post_counts[gname] = get_post_count(url)

total_posts = sum(v for v in post_counts.values() if v >= 0)

# ─────────────────────────────────────────────
# 요약 메트릭 카드 4개
# ─────────────────────────────────────────────

total_galleries = len(df)
error_count = sum(1 for v in df[last_result_col] if "에러" in str(v)) if last_result_col else 0
normal_count = total_galleries - error_count
latest_run = str(df[last_run_col].iloc[0]) if last_run_col else ""

m1, m2, m3, m4 = st.columns(4)
for col, icon, value, label, color in [
    (m1, "🗂️",  f"{total_galleries}개",          "등록 갤러리",    "#3b82f6"),
    (m2, "📄",  f"{total_posts:,}건",              "총 수집 게시글", "#10b981"),
    (m3, "✅",  f"{normal_count} / {total_galleries}", "정상 갤러리", "#f59e0b"),
    (m4, "🕐",  get_time_ago(latest_run),           "마지막 실행",   "#8b5cf6"),
]:
    with col:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid {color};">
            <div class="metric-icon">{icon}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 갤러리별 수집 현황
# ─────────────────────────────────────────────

st.markdown('<div class="section-title">📋 갤러리별 수집 현황</div>', unsafe_allow_html=True)

# 컬럼 헤더
hc = st.columns([3.5, 2.5, 2, 2, 1.6])
for col, label in zip(hc, ["갤러리", "수집 상태", "총 게시글", "마지막 실행", "바로가기"]):
    col.markdown(f"<p class='table-header'>{label}</p>", unsafe_allow_html=True)

# 갤러리 행
for idx, row in df.iterrows():
    color      = CARD_COLORS[idx % len(CARD_COLORS)]
    gname      = str(row.get(name_col, ''))
    gid        = str(row.get(id_col, '')) if id_col else ''
    result_msg = str(row.get(last_result_col, '')) if last_result_col else ''
    last_run   = str(row.get(last_run_col, '')) if last_run_col else ''
    sheet_url  = str(row.get(sheet_url_col, '')) if sheet_url_col else ''
    count      = post_counts.get(gname, -1)
    count_str  = f"{count:,}건" if count >= 0 else "? 건"

    c1, c2, c3, c4, c5 = st.columns([3.5, 2.5, 2, 2, 1.6])

    with c1:
        st.markdown(f"""
        <div class="gall-name-block" style="border-left: 5px solid {color};">
            <div class="gall-name">{gname}</div>
            <div class="gall-id">{gid}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="meta-block">{get_badge_html(result_msg)}</div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="meta-block" style="font-weight:700; color:#1f2937;">
            📄 {count_str}
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="meta-block" style="color:#6b7280;">
            🕐 {get_time_ago(last_run)}
        </div>
        """, unsafe_allow_html=True)

    with c5:
        if sheet_url.startswith('http'):
            st.link_button("시트 열기 →", sheet_url, use_container_width=True)

    st.markdown("<div class='row-gap'></div>", unsafe_allow_html=True)

st.markdown("<div style='margin-top:4px; font-size:12px; color:#9ca3af; text-align:right;'>💡 총 게시글 수는 5분 주기로 갱신됩니다.</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 온보딩 가이드
# ─────────────────────────────────────────────

st.markdown("---")
with st.expander("📚 온보딩(과거 데이터) 스크래퍼 실행 가이드"):
    st.markdown("디시인사이드 봇 차단 정책으로 인해, **온보딩 스크래퍼는 반드시 로컬 PC에서 실행**해야 합니다.")
    st.markdown("""
1. **`git clone [퍼블릭 깃허브 주소]`** 로 코드를 로컬에 다운로드합니다.
2. 폴더 최상단에 `.env` 파일을 만들고 아래 내용을 입력합니다:
   ```
   GCP_CREDENTIALS={...서비스계정 JSON 전체...}
   MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/...
   ```
3. **`pip install -r requirements.txt`** 로 필수 패키지를 설치합니다.
4. **`python onboarding_scraper.py`** 실행 후 갤러리 번호와 수집 시작 날짜를 입력합니다.
    """)

st.markdown("""
<div style="text-align:right; color:#9ca3af; font-size:12px; padding: 8px 0 0;">
    시스템 총괄 PM : 김무길 &nbsp;|&nbsp; DC-Pickaxe v2.0
</div>
""", unsafe_allow_html=True)

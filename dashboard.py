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

header_html = (
    "<div style='background-color:#FEE500; padding:15px; border-radius:10px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>"
    "<h2 style='color:#333333; margin:0; text-align:center;'>⛏️ DC-Pickaxe 실시간 수집 관제탑</h2>"
    "</div>"
)
st.markdown(header_html, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_master_data():
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        return None
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        return None
    master_sheet = client.open_by_url(master_url).sheet1
    records = master_sheet.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in records])


def get_status_badge(result_msg):
    result_msg = str(result_msg).strip()
    if not result_msg:
        return "⚪ 미실행"
    if "에러" in result_msg:
        return f"❌ {result_msg}"
    if "새 글 없음" in result_msg:
        return "✅ 새 글 없음"
    if "개 수집" in result_msg:
        return f"🟢 {result_msg}"
    return result_msg


def get_time_ago(time_str):
    time_str = str(time_str).strip()
    if not time_str:
        return "없음"
    try:
        KST = timezone(timedelta(hours=9))
        last_run = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        now = datetime.now(KST)
        minutes = int((now - last_run).total_seconds() / 60)
        if minutes < 1:
            return "방금 전"
        elif minutes < 60:
            return f"{minutes}분 전"
        elif minutes < 1440:
            return f"{minutes // 60}시간 전"
        else:
            return f"{minutes // 1440}일 전"
    except Exception:
        return time_str


# 새로고침 버튼
col_title, col_btn = st.columns([5, 1])
with col_btn:
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

df = load_master_data()

if df is not None and not df.empty:
    st.subheader("📊 갤러리별 수집 현황")

    display_df = df.copy()

    # 마스터 시트 컬럼명 기준으로 상태·경과시간 컬럼 생성
    last_run_col = next((c for c in display_df.columns if '시각' in c or '시간' in c), None)
    last_result_col = next((c for c in display_df.columns if '개수' in c or '결과' in c), None)

    if last_result_col:
        display_df['상태'] = display_df[last_result_col].apply(get_status_badge)
    if last_run_col:
        display_df['마지막 실행'] = display_df[last_run_col].apply(get_time_ago)

    # 핵심 컬럼만 우선 표시 (URL 같은 긴 컬럼 숨김)
    priority_cols = ['갤러리명', '갤러리ID', '상태', '마지막 실행']
    show_cols = [c for c in priority_cols if c in display_df.columns]
    st.dataframe(display_df[show_cols] if show_cols else display_df, use_container_width=True, hide_index=True)

    st.info("💡 위 데이터는 1분 주기로 자동 갱신됩니다. 깃허브 봇은 약 15분 간격으로 실행됩니다.")

    with st.expander("📋 전체 시트 원본 보기"):
        st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.error("데이터를 불러오지 못했습니다. GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")

st.write("---")
st.subheader("📚 온보딩(과거 데이터) 스크래퍼 실행 가이드")
st.markdown(
    "디시인사이드 봇 차단 정책으로 인해, 수만 건의 과거 데이터를 긁어오는 "
    "**온보딩 스크래퍼는 반드시 로컬 PC에서 실행**해야 합니다. 아래 절차를 따라주세요."
)

guide_html = (
    "<div style='background-color:#f8f9fa; padding:20px; border-radius:8px; border-left: 5px solid #FEE500;'>"
    "<p style='margin-bottom:5px;'><b>1단계:</b> <code>git clone [퍼블릭_깃허브_주소]</code> 명령어로 코드를 로컬에 다운로드합니다.</p>"
    "<p style='margin-bottom:8px;'><b>2단계:</b> 폴더 최상단에 <code>.env</code> 파일을 만들고 아래 내용을 입력합니다:</p>"
    "<pre style='background:#e9ecef; padding:10px; border-radius:4px; font-size:13px;'>"
    "GCP_CREDENTIALS={...서비스계정 JSON 전체...}\n"
    "MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/..."
    "</pre>"
    "<p style='margin-bottom:5px;'><b>3단계:</b> <code>pip install -r requirements.txt</code> 로 필수 도구를 설치합니다.</p>"
    "<p style='margin-bottom:0;'><b>4단계:</b> 터미널에 <code>python onboarding_scraper.py</code>를 입력하여 실행합니다.</p>"
    "</div>"
)
st.markdown(guide_html, unsafe_allow_html=True)

footer_html = (
    "<hr>"
    "<p style='text-align:right; color:gray; font-size:12px;'>시스템 총괄 PM : 김무길</p>"
)
st.markdown(footer_html, unsafe_allow_html=True)

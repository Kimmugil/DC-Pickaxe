import os
import json
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
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
    if not creds_json: return None
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    master_url = os.environ.get('MASTER_SHEET_URL', "https://docs.google.com/spreadsheets/d/1Uk3_T5QVKFQALI3FhSZxqVIE8b7MW01iuViqONQQXlM/edit?gid=0#gid=0")
    master_sheet = client.open_by_url(master_url).sheet1
    records = master_sheet.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in records])

df = load_master_data()

if df is not None and not df.empty:
    st.subheader("📊 갤러리별 수집 현황")
    st.dataframe(df, use_container_width=True)
    st.info("💡 위 데이터는 1분 주기로 최신화되며, 깃허브 실시간 봇의 동작 상태를 나타냅니다.")
else:
    st.error("데이터를 불러오지 못했습니다. GCP_CREDENTIALS 설정을 확인하세요.")

st.write("---")
st.subheader("📚 온보딩(과거 데이터) 스크래퍼 실행 가이드")
st.markdown("디시인사이드 봇 차단 정책으로 인해, 수만 건의 과거 데이터를 긁어오는 **온보딩 스크래퍼는 반드시 로컬 PC에서 실행**해야 합니다. 아래 절차를 따라주세요.")

# 가이드라인 HTML 적용
guide_html = (
    "<div style='background-color:#f8f9fa; padding:20px; border-radius:8px; border-left: 5px solid #FEE500;'>"
    "<p style='margin-bottom:5px;'><b>1단계:</b> <code>git clone [퍼블릭_깃허브_주소]</code> 명령어로 코드를 로컬에 다운로드합니다.</p>"
    "<p style='margin-bottom:5px;'><b>2단계:</b> 폴더 최상단에 <code>.env</code> 파일을 만들고 구글 API 키를 넣습니다.</p>"
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
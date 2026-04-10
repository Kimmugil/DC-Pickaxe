import os
import json
import time
import random
import urllib3
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.dcinside.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

def get_gspread_client():
    """GCP 서비스 계정으로 Google Sheets 클라이언트를 반환합니다."""
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_url_prefix(gallery_type):
    """갤러리 타입에 따라 URL prefix를 반환합니다."""
    if gallery_type == '일반':
        return "board"
    elif gallery_type == '미니':
        return "mini/board"
    else:
        return "mgallery/board"

def get_post_content(gallery_id, post_id, headers, gallery_type, delay_range=(1.5, 3.0), timeout=6):
    """개별 게시글의 본문 텍스트를 가져옵니다."""
    url_prefix = get_url_prefix(gallery_type)
    view_url = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"
    try:
        time.sleep(random.uniform(*delay_range))
        resp = requests.get(view_url, headers=headers, verify=False, timeout=timeout)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            content_div = soup.select_one('.write_div')
            return content_div.get_text(separator=' ', strip=True) if content_div else ""
        return ""
    except Exception:
        return ""

def parse_date_str(date_str, now):
    """DC Inside 날짜 문자열을 'YYYY-MM-DD HH:MM' 또는 'YYYY-MM-DD' 형식으로 변환합니다."""
    if ':' in date_str:
        return f"{now.strftime('%Y-%m-%d')} {date_str}"
    elif date_str.count('.') == 1:
        return f"{now.year}-{date_str.replace('.', '-')}"
    else:
        return f"20{date_str.replace('.', '-')}"

def extract_engagement(row):
    """게시글 목록 행(row)에서 댓글수, 조회수, 추천수를 추출합니다.

    Returns:
        tuple: (댓글수, 조회수, 추천수) — 모두 문자열
    """
    reply_elem = row.select_one('.reply_num')
    comment_count = reply_elem.text.strip().strip('[]') if reply_elem else "0"

    count_elem = row.select_one('.gall_count')
    view_count = count_elem.text.strip() if count_elem else "0"

    recommend_elem = row.select_one('.gall_recommend')
    recommend_count = recommend_elem.text.strip() if recommend_elem else "0"

    return comment_count, view_count, recommend_count


def is_soft_blocked(soup):
    """DC Inside 소프트 차단 감지: 빈 HTML 골격만 반환할 때 True.

    DC Inside는 차단 시 HTTP 200 + 텍스트 없는 빈 페이지를 반환함.
    실제 갤러리 끝(정상 빈 페이지)과 구분하기 위해 목록 골격 유무로 판단.
    """
    # 목록 테이블 골격이 있으면 정상 (빈 갤러리도 뼈대는 있음)
    if soup.select_one('tbody.listwrap2, table.gall_list') is not None:
        return False
    # 골격 없고 차단 키워드가 있으면 명시적 차단
    body_text = soup.get_text().lower()
    for sig in ['잠시 후 다시', '비정상적인 접근', 'blocked', 'captcha', '자동입력 방지']:
        if sig.lower() in body_text:
            return True
    # 골격도 없고 키워드도 없으면 소프트 차단 (빈 응답)
    return True

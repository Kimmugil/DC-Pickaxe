import os
import json
import time
import random
import urllib3
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [수정 필수] 마스터 제어 시트의 URL을 여기에 넣어줘! ---
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Uk3_T5QVKFQALI3FhSZxqVIE8b7MW01iuViqONQQXlM/edit?gid=0#gid=0"

def get_gspread_client():
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_post_content(gallery_id, post_id, headers):
    view_url = f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}"
    try:
        time.sleep(random.uniform(2.0, 4.0)) 
        resp = requests.get(view_url, headers=headers, verify=False, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            content_div = soup.select_one('.write_div')
            return content_div.get_text(separator=' ', strip=True) if content_div else ""
        return ""
    except Exception: return ""

def scrape_past_by_date(gallery_id, existing_ids, target_date):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive"
    }
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    all_past_posts = []
    page = 1
    stop_crawling = False
    
    while not stop_crawling:
        print(f"\n[{page}페이지] 탐색 중...")
        list_url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        try:
            response = requests.get(list_url, headers=headers, verify=False, timeout=10)
            if response.status_code != 200:
                print(f"차단 의심(코드 {response.status_code}). 1분 대기...")
                time.sleep(60); continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select('.us-post')
            if not rows: break
                
            for row in rows:
                post_id = row.select_one('.gall_num').text.strip()
                if not post_id.isdigit(): continue
                if post_id in existing_ids: continue
                    
                date_str = row.select_one('.gall_date').text.strip()
                if ':' in date_str:
                    date_val = f"{now.strftime('%Y-%m-%d')} {date_str}"
                    post_date = now.date()
                elif date_str.count('.') == 1:
                    date_val = f"{now.year}-{date_str.replace('.', '-')}"
                    post_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                else:
                    date_val = f"20{date_str.replace('.', '-')}"
                    post_date = datetime.strptime(date_val, "%Y-%m-%d").date()

                if post_date < target_date:
                    print(f"\n목표 날짜({target_date}) 도달. 종료!")
                    stop_crawling = True; break

                title_elem = row.select_one('.gall_tit > a:not(.reply_num)')
                title = title_elem.text.strip() if title_elem else ""
                writer = row.select_one('.gall_writer')['data-nick']
                
                content = get_post_content(gallery_id, post_id, headers)
                all_past_posts.append([post_id, title, content, writer, date_val, f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}", "0", "0", "0"])
                print(f" - 수집 완료: {title[:15]}... ({date_val})")
                
        except Exception as e: print(f"에러: {e}"); break
            
        if not stop_crawling:
            page += 1
            time.sleep(random.uniform(3.0, 5.0))
    return all_past_posts

def main():
    client = get_gspread_client()
    
    # 1. 마스터 시트에서 갤러리 목록 가져오기
    master_sheet = client.open_by_url(MASTER_SHEET_URL).sheet1
    gallery_list = master_sheet.get_all_records()
    
# (앞부분 생략)
    print("\n=== DC-Pickaxe 온보딩 대상 선택 ===")
    for i, g in enumerate(gallery_list):
        # [수정] gallery_id -> 갤러리ID 로 변경
        print(f"[{i}] {g['갤러리명']} ({g['갤러리ID']})")
    
    choice = int(input("\n수집할 갤러리 번호를 입력하세요: "))
    selected = gallery_list[choice]
    
    # [수정] 시트 헤더 이름과 똑같이 맞춰주기!
    gallery_id = selected['갤러리ID']
    target_sheet_url = selected['저장시트 URL']
    
    # 2. 선택된 갤러리의 전용 시트 열기
    sheet = client.open_by_url(target_sheet_url).sheet1
    existing_ids = set([x for x in sheet.col_values(1) if x.isdigit()])
    
    target_date_str = input(f"\n[{selected['갤러리명']}] 언제까지 긁을까요? (YYYY-MM-DD): ")
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    past_posts = scrape_past_by_date(gallery_id, existing_ids, target_date)
    
    if past_posts:
        past_posts.reverse()
        sheet.append_rows(past_posts)
        print(f"\n{len(past_posts)}개 데이터 적재 완료!")
    else:
        print("\n새로운 데이터가 없습니다.")

if __name__ == "__main__":
    main()
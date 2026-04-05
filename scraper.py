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

# 1. SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_google_sheet():
    creds_json = os.environ.get('GCP_CREDENTIALS')
    if not creds_json:
        raise ValueError("GCP_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
    
    creds_dict = json.loads(creds_json)
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 구글 시트 URL
    sheet_url = "https://docs.google.com/spreadsheets/d/10vkTnnqF_Ryu3KIwDr6UA_nYSAPHQWM2ty0yppFxDIs/edit?gid=0#gid=0"
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

def scrape_gallery(gallery_id):
    url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive"
    }

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=6)
        
        if response.status_code != 200:
            print(f"IP 차단 의심: 상태 코드 {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # 한국 시간(KST) 설정
        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST)
        
        rows = soup.select('.us-post')
        for row in rows:
            post_id = row.select_one('.gall_num').text.strip()
            
            # 공지사항 제외
            if not post_id.isdigit():
                continue
                
            # 제목 (댓글수 태그를 제외한 순수 제목만 추출)
            title_elem = row.select_one('.gall_tit > a:not(.reply_num)')
            title = title_elem.text.strip() if title_elem else ""
            
            # 댓글수 추출 (없으면 0)
            reply_elem = row.select_one('.gall_tit .reply_num')
            reply_count = reply_elem.text.strip('[]') if reply_elem else "0"
            
            writer = row.select_one('.gall_writer')['data-nick']
            
            # 날짜 포맷팅 스마트 변환 로직
            date_str = row.select_one('.gall_date').text.strip()
            if ':' in date_str:
                # 오늘 올라온 글 (예: 15:30 -> 2026-04-05 15:30)
                date_val = f"{now.strftime('%Y-%m-%d')} {date_str}"
            elif date_str.count('.') == 1:
                # 올해 올라온 글 (예: 04.05 -> 2026-04-05)
                date_val = f"{now.year}-{date_str.replace('.', '-')}"
            elif date_str.count('.') == 2:
                # 과거에 올라온 글 (예: 23.04.05 -> 2023-04-05)
                date_val = f"20{date_str.replace('.', '-')}"
            else:
                date_val = date_str
                
            # 조회수 및 추천수 추출
            views = row.select_one('.gall_count').text.strip()
            recommends = row.select_one('.gall_recommend').text.strip()
            
            # 데이터 배열에 추가 (순서: 글번호, 제목, 작성자, 작성일, 댓글수, 조회수, 추천수)
            posts.append([post_id, title, writer, date_val, reply_count, views, recommends])
            
        return posts

    except Exception as e:
        print(f"크롤링 중 에러 발생: {e}")
        return []

def main():
    gallery_id = "maplerpg"
    sheet = get_google_sheet()
    
    existing_ids_list = sheet.col_values(1)
    existing_ids = set(existing_ids_list)
    
    new_posts = scrape_gallery(gallery_id)
    time.sleep(random.uniform(0.5, 2.0))
    
    posts_to_add = []
    for post in new_posts:
        post_id = post[0]
        if post_id not in existing_ids:
            posts_to_add.append(post)
    
    if posts_to_add:
        posts_to_add.reverse()
        sheet.append_rows(posts_to_add)
        print(f"{len(posts_to_add)}개의 새로운 글을 업데이트했습니다.")
    else:
        print("새로 업데이트할 글이 없습니다.")

if __name__ == "__main__":
    main()

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
    
    sheet_url = "https://docs.google.com/spreadsheets/d/10vkTnnqF_Ryu3KIwDr6UA_nYSAPHQWM2ty0yppFxDIs/edit?gid=0#gid=0"
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

def get_post_content(gallery_id, post_id, headers):
    view_url = f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}"
    try:
        time.sleep(random.uniform(1.5, 3.0)) 
        resp = requests.get(view_url, headers=headers, verify=False, timeout=6)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            content_div = soup.select_one('.write_div')
            if content_div:
                return content_div.get_text(separator=' ', strip=True)
        return ""
    except Exception:
        return ""

def scrape_gallery(gallery_id, existing_ids, is_first_run):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive"
    }

    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    
    all_new_posts = []
    page = 1
    
    # [핵심] 첫 실행이면 딱 1페이지만 긁고 종료! 아니면 최대 50페이지까지 탐색.
    max_pages = 1 if is_first_run else 50 
    stop_crawling = False
    
    while page <= max_pages and not stop_crawling:
        list_url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        
        try:
            response = requests.get(list_url, headers=headers, verify=False, timeout=6)
            
            if response.status_code != 200:
                print(f"IP 차단 의심: 상태 코드 {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select('.us-post')
            
            if not rows:
                break
                
            for row in rows:
                post_id = row.select_one('.gall_num').text.strip()
                
                if not post_id.isdigit():
                    continue
                    
                if post_id in existing_ids:
                    print(f"{post_id}번 글은 이미 수집됨. 크롤링을 조기 종료합니다.")
                    stop_crawling = True
                    break
                    
                title_elem = row.select_one('.gall_tit > a:not(.reply_num)')
                title = title_elem.text.strip() if title_elem else ""
                
                reply_elem = row.select_one('.gall_tit .reply_num')
                reply_count = reply_elem.text.strip('[]') if reply_elem else "0"
                
                writer = row.select_one('.gall_writer')['data-nick']
                
                date_str = row.select_one('.gall_date').text.strip()
                if ':' in date_str:
                    date_val = f"{now.strftime('%Y-%m-%d')} {date_str}"
                elif date_str.count('.') == 1:
                    date_val = f"{now.year}-{date_str.replace('.', '-')}"
                elif date_str.count('.') == 2:
                    date_val = f"20{date_str.replace('.', '-')}"
                else:
                    date_val = date_str
                    
                views = row.select_one('.gall_count').text.strip()
                recommends = row.select_one('.gall_recommend').text.strip()
                
                post_link = f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}"
                
                content = get_post_content(gallery_id, post_id, headers)
                
                all_new_posts.append([post_id, title, content, writer, date_val, post_link, reply_count, views, recommends])
                
        except Exception as e:
            print(f"크롤링 중 에러 발생: {e}")
            break
            
        print(f"{page}페이지 수집 완료.")
        page += 1
        time.sleep(random.uniform(1.0, 2.0))
        
    return all_new_posts

def main():
    gallery_id = "maplerpg"
    sheet = get_google_sheet()
    
    # 시트의 A열(글번호) 데이터를 싹 가져옴
    existing_ids_list = sheet.col_values(1)
    
    # 빈 칸이나 '글번호' 같은 한글 제목을 제외하고, 오직 '숫자(글번호)'만 뽑아서 저장
    existing_ids = set([x for x in existing_ids_list if x.isdigit()])
    
    # 시트에 저장된 숫자(글번호)가 0개라면? = 이번이 완전 첫 실행이다!
    is_first_run = (len(existing_ids) == 0)
    
    if is_first_run:
        print("시트가 비어있는 것을 확인했습니다. 첫 실행 모드(1페이지만 수집)로 작동합니다.")
    else:
        print("새로운 게시글 탐색을 시작합니다...")
        
    new_posts = scrape_gallery(gallery_id, existing_ids, is_first_run)
    
    if new_posts:
        new_posts.reverse()
        sheet.append_rows(new_posts)
        print(f"총 {len(new_posts)}개의 새로운 글을 구글 시트에 업데이트했습니다!")
    else:
        print("새로 업데이트할 글이 없습니다.")

if __name__ == "__main__":
    main()

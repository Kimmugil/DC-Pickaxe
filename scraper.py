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
    max_pages = 1 if is_first_run else 50 
    stop_crawling = False
    
    while page <= max_pages and not stop_crawling:
        list_url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        try:
            response = requests.get(list_url, headers=headers, verify=False, timeout=6)
            if response.status_code != 200:
                print(f"[{gallery_id}] IP 차단 의심: 상태 코드 {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select('.us-post')
            if not rows: break
                
            for row in rows:
                post_id = row.select_one('.gall_num').text.strip()
                if not post_id.isdigit(): continue
                    
                if post_id in existing_ids:
                    print(f"[{gallery_id}] {post_id}번 글 중복 발견. 크롤링 조기 종료.")
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
            print(f"[{gallery_id}] 크롤링 에러: {e}")
            break
            
        page += 1
        time.sleep(random.uniform(1.0, 2.0))
        
    return all_new_posts

def main():
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")
        
    client = get_gspread_client()
    master_sheet = client.open_by_url(master_url).sheet1
    gallery_list = master_sheet.get_all_records()
    
    KST = timezone(timedelta(hours=9))
    
    # 마스터 시트에 등록된 모든 갤러리를 순회
    for idx, g in enumerate(gallery_list):
        gallery_id = g['갤러리ID']
        sheet_url = g['저장시트 URL']
        gallery_name = g['갤러리명']
        
        print(f"\n>>> [{gallery_name}] 수집을 시작합니다...")
        
        try:
            target_sheet = client.open_by_url(sheet_url).sheet1
            existing_ids_list = target_sheet.col_values(1)
            existing_ids = set([x for x in existing_ids_list if x.isdigit()])
            
            is_first_run = (len(existing_ids) == 0)
            
            new_posts = scrape_gallery(gallery_id, existing_ids, is_first_run)
            
            if new_posts:
                new_posts.reverse()
                target_sheet.append_rows(new_posts)
                result_msg = f"{len(new_posts)}개 업데이트"
            else:
                result_msg = "새 글 없음"
                
            print(f"[{gallery_name}] 결과: {result_msg}")
            
            # [핵심] 마스터 시트에 '최근 동작 시간'과 '최근 수집 개수' 기록하기
            # 헤더가 1행이므로, 데이터는 idx + 2 행부터 시작됨 (A=1, B=2, C=3, D=4, E=5)
            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            master_sheet.update_cell(idx + 2, 4, now_str)      # 4번째 열(D): 최근 동작 시간
            master_sheet.update_cell(idx + 2, 5, result_msg)   # 5번째 열(E): 최근 수집 개수
            
        except Exception as e:
            print(f"[{gallery_name}] 처리 중 치명적 에러: {e}")
            master_sheet.update_cell(idx + 2, 4, datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'))
            master_sheet.update_cell(idx + 2, 5, f"에러 발생")
            
        # 갤러리 하나 끝날 때마다 서버 차단 방지를 위해 길게 휴식
        time.sleep(random.uniform(3.0, 5.0))

if __name__ == "__main__":
    main()
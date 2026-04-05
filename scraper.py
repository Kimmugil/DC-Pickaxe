import os
import json
import time
import random
import urllib3
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# 1. SSL 인증서 경고 무시 (필수 요청 사항)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_google_sheet():
    # GitHub Secrets에서 환경변수로 주입받은 인증 정보 사용 (보안 필수)
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
    
    # 본인의 구글 시트 URL 또는 문서 ID 입력 (이 부분은 시트 주소로 교체 필요)
    sheet_url = "구글_시트_URL을_여기에_입력하세요"
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

def scrape_gallery(gallery_id):
    url = f"https://gall.dcinside.com/board/lists/?id={gallery_id}"
    
    # 2. 우회 헤더 고정 (필수 요청 사항)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive"
    }

    try:
        # 3. 타임아웃 6초 및 인증서 검증 해제 (필수 요청 사항)
        response = requests.get(url, headers=headers, verify=False, timeout=6)
        
        # 4. HTTP 상태 코드가 200이 아닐 경우 예외 처리
        if response.status_code != 200:
            print(f"IP 차단 의심: 상태 코드 {response.status_code}")
            return [] # 프로세스가 죽지 않고 빈 리스트를 반환하여 안전하게 종료
            
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # 게시글 목록 파싱 (디시인사이드 HTML 구조에 맞게 작성)
        rows = soup.select('.us-post')
        for row in rows:
            post_id = row.select_one('.gall_num').text.strip()
            title = row.select_one('.gall_tit a').text.strip()
            writer = row.select_one('.gall_writer')['data-nick']
            date = row.select_one('.gall_date').text.strip()
            
            # 공지사항(숫자가 아닌 글 번호)은 수집에서 제외
            if not post_id.isdigit():
                continue
                
            posts.append([post_id, title, writer, date])
            
        return posts

    except Exception as e:
        print(f"크롤링 중 에러 발생: {e}")
        return []

def main():
    gallery_id = "수집할_갤러리_ID_입력"
    sheet = get_google_sheet()
    
    # 기존에 시트에 있는 '글 번호(A열)' 가져와서 Set으로 변환 (중복 방지 효율화)
    existing_ids_list = sheet.col_values(1)
    existing_ids = set(existing_ids_list)
    
    # 디시인사이드 스크래핑
    new_posts = scrape_gallery(gallery_id)
    
    # 5. 인간적인 랜덤 딜레이 적용 (목록/본문 요청 사이)
    time.sleep(random.uniform(0.5, 2.0))
    
    posts_to_add = []
    for post in new_posts:
        post_id = post[0]
        if post_id not in existing_ids:
            posts_to_add.append(post)
    
    # 새로운 글이 있다면 구글 시트에 일괄 추가
    if posts_to_add:
        # 가장 오래된 글부터 시트에 쌓이도록 순서 뒤집기
        posts_to_add.reverse()
        sheet.append_rows(posts_to_add)
        print(f"{len(posts_to_add)}개의 새로운 글을 업데이트했습니다.")
    else:
        print("새로 업데이트할 글이 없습니다.")

if __name__ == "__main__":
    main()

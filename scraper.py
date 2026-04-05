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
    
    # 무길공주의 구글 시트 URL 적용 완료!
    sheet_url = "https://docs.google.com/spreadsheets/d/10vkTnnqF_Ryu3KIwDr6UA_nYSAPHQWM2ty0yppFxDIs/edit?gid=0#gid=0"
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

def scrape_gallery(gallery_id):
    # [수정됨] 마이너 갤러리 전용 주소 (mgallery) 반영 완료!
    url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}"
    
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
            return []
            
        # [수정됨] 혹시 디시에서 빈 화면이나 캡챠를 주는지 확인하기 위한 로그 출력
        print("페이지 내용 미리보기:", response.text[:500])
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # 게시글 목록 파싱 
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
    # [수정됨] 메이플스토리 마이너 갤러리 ID 적용 완료!
    gallery_id = "maplerpg"
    sheet = get_google_sheet()
    
    # 기존에 시트에 있는 '글 번호(A열)' 가져와서 Set으로 변환 (중복 방지 효율화)
    existing_ids_list = sheet.col_values(1)
    existing_ids = set(existing_ids_list)
    
    # 디시인사이드 스크래핑
    new_posts = scrape_gallery(gallery_id)
    
    # 5. 인간적인 랜덤 딜레이 적용 
    time.sleep(random.uniform(0.5, 2.0))
    
    posts_to_add = []
    for post in new_posts:
        post_id = post[0]
        if post_id not in existing_ids:
            posts_to_add.append(post)
    
    # 새로운 글이 있다면 구글 시트에 일괄 추가
    if posts_to_add:
        posts_to_add.reverse() # 오래된 글부터 시트에 쌓이도록
        sheet.append_rows(posts_to_add)
        print(f"{len(posts_to_add)}개의 새로운 글을 업데이트했습니다.")
    else:
        print("새로 업데이트할 글이 없습니다.")

if __name__ == "__main__":
    main()

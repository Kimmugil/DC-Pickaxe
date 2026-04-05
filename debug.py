import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# 던파키우기 갤러리 1페이지 고정
url = "https://gall.dcinside.com/mgallery/board/lists/?id=gssc&page=1"

print("=== 디시인사이드 1페이지 봇 시야 확인 (디버깅) ===")
try:
    resp = requests.get(url, headers=headers, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    rows = soup.select('.us-post')
    
    print(f"\n봇이 발견한 게시글 수: {len(rows)}개\n")
    
    for row in rows:
        gall_num = row.select_one('.gall_num').text.strip() if row.select_one('.gall_num') else "X"
        title_elem = row.select_one('.gall_tit a:not(.reply_num)')
        title = title_elem.text.strip() if title_elem else "X"
        
        print(f"글번호: {gall_num} | 제목: {title}")
        
except Exception as e:
    print("에러 발생:", e)
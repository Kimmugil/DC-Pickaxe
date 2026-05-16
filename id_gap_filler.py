"""
DC-Pickaxe ID 갭 채우기

갤러리 시트의 글 번호(A열) 시퀀스에서 누락된 ID를 탐지하고 해당 글을 수집합니다.
삭제/비공개 글은 자동으로 건너뜁니다.

수동 실행: python id_gap_filler.py <gallery_id>
워크플로우: GALLERY_ID 환경변수로 전달
"""
import os
import sys
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import get_gspread_client, get_url_prefix, DEFAULT_HEADERS

load_dotenv()

REQUEST_TIMEOUT = 10
FETCH_DELAY     = (1.5, 2.5)
BATCH_SIZE      = 30
MAX_RUNTIME_MIN = 60

DELETED_SIGNALS = ['존재하지 않는 게시물', '삭제된 게시물', '해당 게시물을 찾을 수 없']


def fetch_post(gallery_id, post_id, url_prefix):
    """뷰 페이지에서 게시글 전체 정보를 수집. 삭제/없는 글이면 None 반환."""
    url = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"
    try:
        time.sleep(random.uniform(*FETCH_DELAY))
        resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        body_text = soup.get_text()

        if any(s in body_text for s in DELETED_SIGNALS):
            return None

        # 제목
        title_elem = soup.select_one('.title_subject')
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # 작성자
        writer_elem = soup.select_one('.gall_writer')
        writer = writer_elem.get('data-nick', '') if writer_elem else ''

        # 날짜 — 뷰 페이지: "YYYY.MM.DD HH:MM:SS" 형식
        date_str = ''
        date_elem = soup.select_one('.fl_l.temp_date')
        if date_elem:
            raw = date_elem.get_text(strip=True)  # e.g. "2024.01.15 14:30:25"
            try:
                dt = datetime.strptime(raw[:16], '%Y.%m.%d %H:%M')
                date_str = dt.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                date_str = raw[:16]

        # 본문
        content_div = soup.select_one('.write_div')
        content = content_div.get_text(separator=' ', strip=True) if content_div else ''

        # 조회수
        view_elem = soup.select_one('.gall_count')
        view_count = view_elem.get_text(strip=True).replace(',', '') if view_elem else '0'

        # 추천수
        recommend_elem = soup.select_one('.up_num_box .up_num')
        recommend_count = recommend_elem.get_text(strip=True) if recommend_elem else '0'

        # 댓글수 — 뷰 페이지 헤더 영역
        comment_elem = soup.select_one('.cmt_title_num')
        comment_count = comment_elem.get_text(strip=True) if comment_elem else '0'

        return [post_id, title, content, writer, date_str, url,
                comment_count, view_count, recommend_count]

    except Exception as e:
        print(f"  [ID {post_id}] 에러: {e}")
        return None


def main():
    gallery_id = os.environ.get('GALLERY_ID', '').strip()
    if not gallery_id and len(sys.argv) > 1:
        gallery_id = sys.argv[1].strip()
    if not gallery_id:
        print("갤러리 ID를 지정해주세요.\n사용법: python id_gap_filler.py <gallery_id>")
        sys.exit(1)

    KST = timezone(timedelta(hours=9))
    start_time = datetime.now(KST)
    deadline = start_time + timedelta(minutes=MAX_RUNTIME_MIN)

    client = get_gspread_client()
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    # 마스터 시트에서 갤러리 정보 조회
    master_sheet = client.open_by_url(master_url).sheet1
    gallery_list = [{k.strip(): v for k, v in r.items()} for r in master_sheet.get_all_records()]
    gallery_info = next((g for g in gallery_list if g.get('갤러리ID') == gallery_id), None)

    if not gallery_info:
        print(f"마스터 시트에서 '{gallery_id}'를 찾을 수 없습니다.")
        sys.exit(1)

    gallery_name = gallery_info.get('갤러리명', gallery_id)
    sheet_url    = gallery_info.get('저장시트 URL', '').strip()
    gallery_type = gallery_info.get('갤러리타입', '마이너').strip()
    url_prefix   = get_url_prefix(gallery_type)

    print(f"\n{'='*60}")
    print(f"  DC-Pickaxe ID 갭 채우기")
    print(f"  갤러리: [{gallery_name}] ({gallery_id})")
    print(f"  실행: {start_time.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  종료 예정: {deadline.strftime('%H:%M')} KST (+{MAX_RUNTIME_MIN}분)")
    print(f"{'='*60}\n")

    # 시트에서 기존 ID 목록 로드
    sheet = client.open_by_url(sheet_url).sheet1
    existing_raw = [v for v in sheet.col_values(1) if str(v).isdigit()]
    existing_ids = set(existing_raw)

    if len(existing_ids) < 2:
        print("수집된 글이 너무 적어 갭 탐지를 건너뜁니다.")
        return

    min_id = min(int(v) for v in existing_ids)
    max_id = max(int(v) for v in existing_ids)
    full_range = set(str(i) for i in range(min_id, max_id + 1))
    missing_ids = sorted(full_range - existing_ids, key=lambda x: int(x))

    print(f"ID 범위: {min_id} ~ {max_id} (총 {max_id - min_id + 1}개)")
    print(f"수집된 글: {len(existing_ids)}개")
    print(f"누락 ID: {len(missing_ids)}개 (삭제된 글 포함)\n")

    if not missing_ids:
        print("누락된 ID가 없습니다.")
        return

    filled = 0
    deleted = 0
    error = 0
    batch = []

    for i, post_id in enumerate(missing_ids, 1):
        if datetime.now(KST) >= deadline:
            print(f"\n⏰ 시간 제한 도달 — {i-1}/{len(missing_ids)}개 처리 후 중단")
            break

        if i % 50 == 0 or i == 1:
            print(f"진행: {i}/{len(missing_ids)} | 수집 {filled}건 / 삭제 {deleted}건", end='\r')

        result = fetch_post(gallery_id, post_id, url_prefix)

        if result is None:
            deleted += 1
            continue

        batch.append(result)
        existing_ids.add(post_id)
        filled += 1

        if len(batch) >= BATCH_SIZE:
            sheet.append_rows(batch, value_input_option='RAW')
            batch = []
            time.sleep(1.0)

    if batch:
        sheet.append_rows(batch, value_input_option='RAW')

    elapsed = int((datetime.now(KST) - start_time).total_seconds() / 60)
    print(f"\n{'='*60}")
    print(f"  완료! 수집 {filled}건 | 삭제/없음 {deleted}건 | 소요: {elapsed}분")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

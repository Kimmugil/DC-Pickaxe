import os
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import get_gspread_client, get_url_prefix, get_post_content, parse_date_str, extract_engagement, DEFAULT_HEADERS

load_dotenv()


def scrape_past_by_date(gallery_id, existing_ids, target_date, gallery_type):
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    url_prefix = get_url_prefix(gallery_type)

    all_past_posts = []
    seen_in_this_run = set()
    page = 1
    stop_crawling = False

    while not stop_crawling:
        print(f"\n[{page}페이지] 탐색 중...")
        list_url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
        try:
            response = requests.get(list_url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
            if response.status_code != 200:
                print(f"차단 의심(코드 {response.status_code}). 1분 대기...")
                time.sleep(60)
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select('.us-post')
            if not rows:
                break

            valid_posts_on_page = 0
            duplicates_in_run = 0

            for row in rows:
                gall_num_elem = row.select_one('.gall_num')
                gall_num_text = gall_num_elem.text.strip() if gall_num_elem else ""

                gall_subject_elem = row.select_one('.gall_subject')
                gall_subject_text = gall_subject_elem.text.strip() if gall_subject_elem else ""

                is_notice = (
                    not gall_num_text.isdigit()
                    or '공지' in gall_subject_text
                    or row.select_one('.icon_notice') is not None
                )

                title_elem = row.select_one('.gall_tit a:not(.reply_num)')
                if not title_elem:
                    continue

                href = title_elem.get('href', '')
                if 'no=' not in href:
                    continue

                post_id = href.split('no=')[1].split('&')[0]
                if not post_id.isdigit():
                    continue

                valid_posts_on_page += 1

                if post_id in seen_in_this_run:
                    duplicates_in_run += 1
                    continue

                seen_in_this_run.add(post_id)
                if post_id in existing_ids:
                    continue

                date_str = row.select_one('.gall_date').text.strip()
                date_val = parse_date_str(date_str, now)

                # 날짜 비교용 date 객체 추출
                if ':' in date_str:
                    post_date = now.date()
                else:
                    post_date = datetime.strptime(date_val, "%Y-%m-%d").date()

                if not is_notice and post_date < target_date:
                    print(f"\n일반 게시글 목표 날짜({target_date}) 도달. 종료!")
                    stop_crawling = True
                    break

                title = title_elem.text.strip()
                writer = row.select_one('.gall_writer')['data-nick']
                comment_count, view_count, recommend_count = extract_engagement(row)
                content = get_post_content(
                    gallery_id, post_id, DEFAULT_HEADERS, gallery_type,
                    delay_range=(2.0, 4.0), timeout=10
                )
                post_link = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"

                all_past_posts.append([
                    post_id, title, content, writer, date_val,
                    post_link, comment_count, view_count, recommend_count
                ])
                print(f" - 수집 완료: {title[:20]}... ({date_val})")

            if valid_posts_on_page > 0 and valid_posts_on_page == duplicates_in_run:
                print("\n더 이상 과거 글이 존재하지 않습니다 (마지막 페이지 도달). 수집을 조기 종료합니다.")
                break

        except Exception as e:
            print(f"에러: {e}")
            break

        if not stop_crawling:
            page += 1
            time.sleep(random.uniform(3.0, 5.0))

    return all_past_posts


def main():
    client = get_gspread_client()

    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다. .env 파일에 MASTER_SHEET_URL=... 을 추가하세요.")

    master_sheet = client.open_by_url(master_url).sheet1

    raw_records = master_sheet.get_all_records()
    gallery_list = [{k.strip(): v for k, v in record.items()} for record in raw_records]

    print("\n=== DC-Pickaxe 온보딩 대상 선택 ===")
    for i, g in enumerate(gallery_list):
        print(f"[{i}] {g.get('갤러리명', '이름없음')} ({g.get('갤러리ID', 'ID없음')} - {g.get('갤러리타입', '마이너')})")

    choice = int(input("\n수집할 갤러리 번호를 입력하세요: "))
    selected = gallery_list[choice]

    gallery_id = selected['갤러리ID']
    target_sheet_url = selected['저장시트 URL']
    gallery_type = selected.get('갤러리타입', '마이너').strip()

    sheet = client.open_by_url(target_sheet_url).sheet1
    existing_ids = set([x for x in sheet.col_values(1) if x.isdigit()])

    target_date_str = input(f"\n[{selected['갤러리명']}] 언제까지 긁을까요? (YYYY-MM-DD): ")
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    past_posts = scrape_past_by_date(gallery_id, existing_ids, target_date, gallery_type)

    if past_posts:
        past_posts.reverse()
        sheet.append_rows(past_posts)
        print(f"\n{len(past_posts)}개 데이터 적재 완료!")
    else:
        print("\n새로운 데이터가 없습니다.")


if __name__ == "__main__":
    main()

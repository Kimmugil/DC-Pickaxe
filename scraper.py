import os
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from utils import get_gspread_client, get_url_prefix, get_post_content, parse_date_str, extract_engagement, DEFAULT_HEADERS, is_soft_blocked


def scrape_gallery(gallery_id, existing_ids, is_first_run, gallery_type):
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    url_prefix = get_url_prefix(gallery_type)

    all_new_posts = []
    page = 1
    max_pages = 1 if is_first_run else 100
    stop_crawling = False
    consecutive_known = 0        # 연속으로 기존 글을 만난 횟수
    STOP_AFTER_KNOWN  = 5        # 이 수만큼 연속 기존 글이면 수집 완료로 판단

    while page <= max_pages and not stop_crawling:
        list_url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
        try:
            response = requests.get(list_url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
            if response.status_code != 200:
                print(f"[{gallery_id}] 응답 {response.status_code} — 30초 후 재시도")
                time.sleep(30)
                response = requests.get(list_url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
                if response.status_code != 200:
                    print(f"[{gallery_id}] 재시도 실패 ({response.status_code}) — 이 페이지 건너뜀")
                    page += 1
                    continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # 소프트 차단 감지: 골격 없이 빈 페이지 반환 시 60초 대기 후 재시도
            if is_soft_blocked(soup):
                print(f"[{gallery_id}] ⚠️  소프트 차단 감지 (페이지 {page}) — 60초 대기 후 재시도")
                time.sleep(60)
                response = requests.get(list_url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                if is_soft_blocked(soup):
                    print(f"[{gallery_id}] 재시도 후에도 차단 — 이번 수집 중단")
                    break

            rows = soup.select('.us-post')
            if not rows:
                break

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

                # 공지글은 신규/기존 무관하게 항상 건너뜀 (크래시 방지 + 중복 방지)
                if is_notice:
                    continue

                if post_id in existing_ids:
                    consecutive_known += 1
                    if consecutive_known >= STOP_AFTER_KNOWN:
                        print(f"[{gallery_id}] 기존 글 {STOP_AFTER_KNOWN}개 연속 — 수집 완료.")
                        stop_crawling = True
                        break
                    continue

                consecutive_known = 0  # 새 글 발견 시 리셋

                title = title_elem.text.strip()
                writer_elem = row.select_one('.gall_writer')
                writer = writer_elem['data-nick'] if writer_elem and writer_elem.has_attr('data-nick') else ""
                date_val = parse_date_str(row.select_one('.gall_date').text.strip(), now)
                comment_count, view_count, recommend_count = extract_engagement(row)
                post_link = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"
                content = get_post_content(gallery_id, post_id, DEFAULT_HEADERS, gallery_type)

                all_new_posts.append([
                    post_id, title, content, writer, date_val,
                    post_link, comment_count, view_count, recommend_count
                ])

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

    raw_records = master_sheet.get_all_records()
    gallery_list = [{k.strip(): v for k, v in record.items()} for record in raw_records]

    KST = timezone(timedelta(hours=9))

    for idx, g in enumerate(gallery_list):
        gallery_id = g.get('갤러리ID')
        sheet_url = g.get('저장시트 URL')
        gallery_name = g.get('갤러리명')
        gallery_type = g.get('갤러리타입', '마이너').strip()

        print(f"\n>>> [{gallery_name}] 수집 시작...")

        try:
            target_sheet = client.open_by_url(sheet_url).sheet1
            existing_ids = set([x for x in target_sheet.col_values(1) if x.isdigit()])
            is_first_run = (len(existing_ids) == 0)

            new_posts = scrape_gallery(gallery_id, existing_ids, is_first_run, gallery_type)

            if new_posts:
                new_posts.reverse()
                target_sheet.append_rows(new_posts)
                result_msg = f"{len(new_posts)}개 수집"
            else:
                result_msg = "새 글 없음"

            print(f"[{gallery_name}] 결과: {result_msg}")

            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            master_sheet.update_cell(idx + 2, 4, now_str)
            master_sheet.update_cell(idx + 2, 5, result_msg)

        except Exception as e:
            print(f"[{gallery_name}] 치명적 에러: {e}")
            master_sheet.update_cell(idx + 2, 4, datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'))
            master_sheet.update_cell(idx + 2, 5, "에러 발생")

        time.sleep(random.uniform(3.0, 5.0))


if __name__ == "__main__":
    main()

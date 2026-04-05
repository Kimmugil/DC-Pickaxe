"""
DC-Pickaxe 온보딩 스크래퍼
- 어제 날짜부터 과거로 역방향 스크래핑
- 게시글 1건 수집 즉시 시트에 저장 (중단해도 저장된 데이터 보존)
- Ctrl+C로 언제든 안전하게 중단 가능
- 오늘 게시글은 건너뜀 (자동 스케줄러 담당)
- N건 수집마다 자동 휴식 (봇 차단 방지)
"""
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import (
    get_gspread_client, get_url_prefix, get_post_content,
    parse_date_str, extract_engagement, DEFAULT_HEADERS
)

load_dotenv()


# ── 봇 차단 방지 설정 ──────────────────────────────────────
# 이 수만큼 수집하면 자동으로 쉬어감 (하루종일 켜둬도 안전)
REST_EVERY_N_POSTS  = 200        # N건마다 쉬기
REST_DURATION_MIN   = 10         # 쉬는 시간 (분)
# ──────────────────────────────────────────────────────────


def scrape_onboarding(gallery_id, existing_ids, gallery_type, sheet):
    """
    어제부터 과거 방향으로 스크래핑하며 수집 즉시 시트에 저장합니다.
    이미 existing_ids에 있는 게시글은 건너뜁니다.
    오늘 게시글은 건너뜁니다 (스케줄러 담당).
    REST_EVERY_N_POSTS건마다 자동 휴식해서 봇 차단을 방지합니다.
    """
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    today = now.date()
    url_prefix = get_url_prefix(gallery_type)

    collected_count = 0
    page = 1
    # 연속으로 새 글이 없는 페이지가 이 수 이상이면 종료 (이미 다 수집됨)
    consecutive_empty_pages = 0
    MAX_EMPTY_PAGES = 5

    print(f"\n{'='*55}")
    print(f"  ⛏️  DC-Pickaxe 온보딩 스크래퍼 시작")
    print(f"{'='*55}")
    print(f"  오늘({today}) 게시글 → 건너뜀 (스케줄러 담당)")
    print(f"  이미 수집된 게시글 {len(existing_ids):,}개 → 건너뜀")
    print(f"  {REST_EVERY_N_POSTS}건마다 {REST_DURATION_MIN}분 자동 휴식 (차단 방지)")
    print(f"  Ctrl+C 로 언제든 안전하게 중단 가능")
    print(f"{'='*55}\n")

    try:
        while True:
            list_url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
            try:
                response = requests.get(list_url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
                if response.status_code != 200:
                    print(f"  ⚠️  차단 의심(코드 {response.status_code}). 1분 대기...")
                    time.sleep(60)
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.select('.us-post')
                if not rows:
                    print(f"  [페이지 {page}] 마지막 페이지 도달. 수집 완료!")
                    break

                new_on_page = 0
                today_skipped = 0

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

                    # 이미 수집된 글 건너뜀
                    if post_id in existing_ids:
                        continue

                    # 날짜 계산
                    date_str = row.select_one('.gall_date').text.strip()
                    date_val = parse_date_str(date_str, now)
                    post_date = today if ':' in date_str else datetime.strptime(date_val, "%Y-%m-%d").date()

                    # 오늘 글 건너뜀 (공지 제외)
                    if not is_notice and post_date >= today:
                        today_skipped += 1
                        continue

                    title = title_elem.text.strip()
                    writer = row.select_one('.gall_writer')['data-nick']
                    comment_count, view_count, recommend_count = extract_engagement(row)
                    content = get_post_content(
                        gallery_id, post_id, DEFAULT_HEADERS, gallery_type,
                        delay_range=(2.0, 4.0), timeout=10
                    )
                    post_link = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"
                    row_data = [
                        post_id, title, content, writer, date_val,
                        post_link, comment_count, view_count, recommend_count
                    ]

                    # ★ 수집 즉시 시트에 저장 ★
                    sheet.append_rows([row_data])
                    existing_ids.add(post_id)
                    new_on_page += 1
                    collected_count += 1
                    print(f"  ✅ [{collected_count:>4}] #{post_id} | {date_val} | {title[:28]}")

                    # ── 자동 휴식 (봇 차단 방지) ──
                    if collected_count % REST_EVERY_N_POSTS == 0:
                        rest_sec = REST_DURATION_MIN * 60
                        print(f"\n  💤 {collected_count}건 수집 완료 → {REST_DURATION_MIN}분 휴식 시작... "
                              f"(재개 예정: {(datetime.now(KST) + timedelta(minutes=REST_DURATION_MIN)).strftime('%H:%M')})")
                        time.sleep(rest_sec)
                        print(f"  ▶️  휴식 종료. 수집 재개!\n")

                # 연속 빈 페이지 카운트 (오늘 글만 있는 페이지는 제외)
                if new_on_page == 0 and today_skipped == 0:
                    consecutive_empty_pages += 1
                    print(f"  [페이지 {page}] 새 글 없음 "
                          f"({consecutive_empty_pages}/{MAX_EMPTY_PAGES} 연속)")
                    if consecutive_empty_pages >= MAX_EMPTY_PAGES:
                        print(f"\n  수집 완료: {MAX_EMPTY_PAGES}페이지 연속 새 글 없음 → 이미 다 수집된 구간입니다.")
                        break
                else:
                    consecutive_empty_pages = 0
                    if today_skipped > 0 and new_on_page == 0:
                        print(f"  [페이지 {page}] 오늘 글 {today_skipped}개 건너뜀 → 다음 페이지로...")

            except Exception as e:
                print(f"\n  에러 발생: {e}")
                break

            page += 1
            time.sleep(random.uniform(3.0, 5.0))

    except KeyboardInterrupt:
        print(f"\n\n  ⛏️  중단됨 (Ctrl+C). 총 {collected_count:,}개 저장 완료. (손실 없음)")

    return collected_count


def main():
    client = get_gspread_client()

    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다. .env 파일을 확인하세요.")

    master_sheet = client.open_by_url(master_url).sheet1
    raw_records = master_sheet.get_all_records()
    gallery_list = [{k.strip(): v for k, v in record.items()} for record in raw_records]

    print("\n=== DC-Pickaxe 온보딩 — 갤러리 선택 ===")
    for i, g in enumerate(gallery_list):
        print(f"  [{i}] {g.get('갤러리명', '이름없음')} "
              f"({g.get('갤러리ID', 'ID없음')} / {g.get('갤러리타입', '마이너')})")

    choice = int(input("\n수집할 갤러리 번호를 입력하세요: "))
    selected = gallery_list[choice]

    gallery_id       = selected['갤러리ID']
    target_sheet_url = selected['저장시트 URL']
    gallery_type     = selected.get('갤러리타입', '마이너').strip()

    sheet = client.open_by_url(target_sheet_url).sheet1
    existing_ids = set(v for v in sheet.col_values(1) if str(v).isdigit())

    total = scrape_onboarding(gallery_id, existing_ids, gallery_type, sheet)
    print(f"\n  최종 적재 완료: {total:,}개\n")


if __name__ == "__main__":
    main()

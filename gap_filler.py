"""
DC-Pickaxe 갭 탐지 + 자동 백필 봇

흐름:
  1. 마스터 시트에서 갤러리 목록 조회
  2. 각 갤러리 시트: 날짜별 게시글 수 집계 → 갭 날짜 탐지
  3. 갭 발견 시: 해당 날짜 구간 역방향 페이지네이션으로 누락 게시글 보충
  4. 결과 로그 출력

운영: GitHub Actions 주 1회 자동 실행 (매주 월요일 06:00 KST)
수동: python gap_filler.py
"""
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import (
    get_gspread_client, get_url_prefix, get_post_content,
    parse_date_str, extract_engagement, DEFAULT_HEADERS,
)

load_dotenv()

# ── 설정 ────────────────────────────────────────────────────────
GAP_DAYS_BACK      = 14    # 최근 며칠까지 검사할지
BASELINE_DAYS      = 60    # 정상 평균 계산에 쓸 기간 (일)
BASELINE_SKIP_DAYS = 3     # 최근 N일은 기준선에서 제외 (수집 진행 중일 수 있음)
GAP_THRESHOLD      = 0.25  # 기준선 중앙값의 이 비율 미만이면 갭
GAP_MIN_POSTS      = 3     # 절대 최소치: 이 건수 미만은 갭 (활성 갤러리 기준)
MAX_PAGES          = 150   # 백필 시 최대 탐색 페이지 수
PAGE_DELAY         = (1.5, 2.5)   # 목록 페이지 간 딜레이 (초)
CONTENT_DELAY      = (1.5, 3.0)   # 본문 수집 딜레이 (초)
BATCH_SIZE         = 30           # 시트 배치 저장 단위
# ────────────────────────────────────────────────────────────────


# ── 갭 탐지 ──────────────────────────────────────────────────────

def get_daily_counts(sheet):
    """시트 E열(날짜)을 읽어 날짜별 게시글 수 반환 {date_str: count}"""
    date_col = sheet.col_values(5)  # E열: 날짜
    counts = defaultdict(int)
    for v in date_col:  # 헤더 없는 시트 (스크래퍼가 헤더 없이 저장)
        if not v:
            continue
        s = str(v)[:10]
        if len(s) == 10 and s[4] == '-':
            counts[s] += 1
    return dict(counts)


def detect_gaps(daily_counts, gallery_name):
    """
    최근 GAP_DAYS_BACK일(오늘 제외) 중 게시글이 비정상적으로 적은 날 반환.
    기준: 최근 BASELINE_DAYS일 중 안정된 구간의 중앙값 × GAP_THRESHOLD
    """
    KST = timezone(timedelta(hours=9))
    today = datetime.now(KST).date()

    # 기준선: 최근 안정 구간의 중앙값
    baseline_vals = []
    for i in range(BASELINE_SKIP_DAYS + 1, BASELINE_DAYS + 1):
        d = str(today - timedelta(days=i))
        if d in daily_counts:
            baseline_vals.append(daily_counts[d])

    if len(baseline_vals) < 3:
        print(f"  [{gallery_name}] 기준선 데이터 부족 — 갭 검사 생략")
        return []

    baseline_vals.sort()
    median = baseline_vals[len(baseline_vals) // 2]
    threshold = max(median * GAP_THRESHOLD, GAP_MIN_POSTS)

    print(f"  [{gallery_name}] 기준 중앙값 {median}건/일 → 갭 임계값 {threshold:.0f}건")

    gaps = []
    for i in range(1, GAP_DAYS_BACK + 1):  # 오늘(i=0) 제외
        d = str(today - timedelta(days=i))
        count = daily_counts.get(d, 0)
        if count < threshold:
            gaps.append(d)
            status = "없음" if count == 0 else f"{count}건"
            print(f"  [{gallery_name}] 🕳  갭 탐지: {d} ({status})")

    return sorted(gaps)  # 오래된 날짜 → 최신 날짜 순


# ── 백필 스크래핑 ─────────────────────────────────────────────────

def backfill_gaps(gallery_id, gap_dates, existing_ids, gallery_type):
    """
    gap_dates 기간의 누락 게시글을 역방향 페이지네이션으로 수집.
    existing_ids로 중복 방지. earliest_gap보다 오래된 날짜를 만나면 종료.
    """
    if not gap_dates:
        return []

    url_prefix = get_url_prefix(gallery_type)
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)

    earliest_gap = gap_dates[0]
    gap_date_set = set(gap_dates)
    all_new = []
    page = 1

    print(f"  [{gallery_id}] 백필 시작 — 대상 날짜: {gap_dates}")

    while page <= MAX_PAGES:
        url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
            if r.status_code != 200:
                print(f"  [{gallery_id}] 페이지 {page} 응답 {r.status_code} — 30초 대기 후 재시도")
                time.sleep(30)
                # 재시도 1회
                r = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=10)
                if r.status_code != 200:
                    page += 1
                    continue

            soup = BeautifulSoup(r.text, 'html.parser')
            rows = soup.select('.us-post')
            if not rows:
                print(f"  [{gallery_id}] 페이지 {page} — 게시글 없음, 갤러리 끝 도달")
                break

            page_new = 0
            passed_earliest = False

            for row in rows:
                gall_num_elem = row.select_one('.gall_num')
                gall_num_text = gall_num_elem.text.strip() if gall_num_elem else ""
                is_notice = (
                    not gall_num_text.isdigit()
                    or row.select_one('.icon_notice') is not None
                )
                if is_notice:
                    continue

                title_elem = row.select_one('.gall_tit a:not(.reply_num)')
                if not title_elem:
                    continue
                href = title_elem.get('href', '')
                if 'no=' not in href:
                    continue
                post_id = href.split('no=')[1].split('&')[0]
                if not post_id.isdigit():
                    continue
                if post_id in existing_ids:
                    continue

                date_str_raw = row.select_one('.gall_date').text.strip()
                date_val = parse_date_str(date_str_raw, now)
                post_date = date_val[:10]

                # 갭보다 오래된 날짜에 도달 → 더 이상 찾을 필요 없음
                if post_date < earliest_gap:
                    passed_earliest = True
                    break

                # 갭 날짜 범위에 해당하는 글만 수집
                if post_date not in gap_date_set:
                    continue

                title = title_elem.text.strip()
                writer_elem = row.select_one('.gall_writer')
                writer = (
                    writer_elem['data-nick']
                    if writer_elem and writer_elem.has_attr('data-nick') else ""
                )
                comment_count, view_count, recommend_count = extract_engagement(row)
                content = get_post_content(
                    gallery_id, post_id, DEFAULT_HEADERS, gallery_type,
                    delay_range=CONTENT_DELAY, timeout=10,
                )
                post_link = (
                    f"https://gall.dcinside.com/{url_prefix}/view/"
                    f"?id={gallery_id}&no={post_id}"
                )
                all_new.append([
                    post_id, title, content, writer, date_val,
                    post_link, comment_count, view_count, recommend_count,
                ])
                existing_ids.add(post_id)
                page_new += 1

            if page_new:
                print(f"  [{gallery_id}] 페이지 {page}: {page_new}건 수집 (누적 {len(all_new)}건)")

            if passed_earliest:
                print(f"  [{gallery_id}] 갭 범위 이전 날짜 도달 — 백필 완료")
                break

        except Exception as e:
            print(f"  [{gallery_id}] 페이지 {page} 에러: {e}")

        page += 1
        time.sleep(random.uniform(*PAGE_DELAY))

    return all_new


# ── 시트 저장 ────────────────────────────────────────────────────

def save_to_sheet(sheet, new_posts):
    for i in range(0, len(new_posts), BATCH_SIZE):
        sheet.append_rows(new_posts[i:i + BATCH_SIZE], value_input_option='RAW')
        time.sleep(1.0)


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    client = get_gspread_client()
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_sheet = client.open_by_url(master_url).sheet1
    gallery_list = [
        {k.strip(): v for k, v in r.items()}
        for r in master_sheet.get_all_records()
    ]

    KST = timezone(timedelta(hours=9))
    total_filled = 0

    print(f"\n{'='*60}")
    print(f"  DC-Pickaxe 갭 탐지 + 백필 봇")
    print(f"  실행: {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  검사 범위: 최근 {GAP_DAYS_BACK}일 | 임계값: 기준선의 {GAP_THRESHOLD*100:.0f}%")
    print(f"{'='*60}\n")

    for g in gallery_list:
        gallery_id   = g.get('갤러리ID', '').strip()
        gallery_name = g.get('갤러리명', gallery_id)
        sheet_url    = g.get('저장시트 URL', '').strip()
        gallery_type = g.get('갤러리타입', '마이너').strip()

        if not gallery_id or not sheet_url:
            continue

        print(f"── [{gallery_name}] 검사 중...")
        try:
            sheet = client.open_by_url(sheet_url).sheet1
            daily_counts = get_daily_counts(sheet)
            gap_dates = detect_gaps(daily_counts, gallery_name)

            if not gap_dates:
                print(f"  [{gallery_name}] 갭 없음 ✓\n")
                continue

            existing_ids = set(v for v in sheet.col_values(1) if str(v).isdigit())
            new_posts = backfill_gaps(gallery_id, gap_dates, existing_ids, gallery_type)

            if new_posts:
                save_to_sheet(sheet, new_posts)
                total_filled += len(new_posts)
                print(f"  [{gallery_name}] ✅ {len(new_posts)}건 보충 완료\n")
            else:
                print(
                    f"  [{gallery_name}] 갭 탐지됐으나 새 글 없음"
                    f" (이미 수집됐거나 실제 비활성 기간)\n"
                )

        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}\n")

        time.sleep(random.uniform(3.0, 5.0))

    print(f"{'='*60}")
    print(f"  완료! 총 {total_filled}건 보충")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

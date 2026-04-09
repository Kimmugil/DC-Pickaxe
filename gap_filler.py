"""
DC-Pickaxe 갭 탐지 + 자동 백필 봇

흐름:
  1. 마스터 시트에서 갤러리 목록 조회
  2. 각 갤러리 시트: 날짜별 게시글 수 집계 → 갭 날짜 탐지
  3. 갭 발견 시: Phase 1 목록 스캔(메타데이터) → Phase 2 async 병렬 본문 수집
  4. 시트 저장

운영: GitHub Actions 매일 03:00 KST 자동 실행
수동: python gap_filler.py
"""
import os
import asyncio
import time
import random
import requests
import aiohttp
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import (
    get_gspread_client, get_url_prefix,
    parse_date_str, extract_engagement, DEFAULT_HEADERS, is_soft_blocked,
)

load_dotenv()

# ── 설정 ────────────────────────────────────────────────────────
MAX_RUNTIME_MIN     = 50    # 1회 실행 최대 시간 (분) — workflow timeout보다 여유있게
GAP_DAYS_BACK       = 30    # 최근 며칠까지 갭 검사 (30일 = 한 달치 전부 커버)
BASELINE_DAYS       = 90    # 정상 평균 계산에 쓸 기간 (일)
BASELINE_SKIP_DAYS  = 3     # 최근 N일은 기준선에서 제외 (수집 진행 중일 수 있음)
GAP_THRESHOLD       = 0.30  # 기준선 중앙값의 이 비율 미만이면 갭
GAP_MIN_POSTS       = 2     # 절대 최소치: 이 건수 미만이면 무조건 갭
MAX_PAGES           = 150   # 백필 시 최대 탐색 페이지 수
PAGE_DELAY          = (1.5, 2.5)   # 목록 페이지 간 딜레이 (초)
CONTENT_CONCURRENCY = 5     # async 본문 동시 수집 수
CONTENT_DELAY       = 0.5   # 본문 요청 간 딜레이 (초)
REQUEST_TIMEOUT     = 12    # 요청 타임아웃 (초)
BATCH_SIZE          = 30    # 시트 배치 저장 단위
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
    기준: 데이터가 있는 날 중 상위 50%의 중앙값 × GAP_THRESHOLD
    (초기 수집이 드문 날이 많아도 기준선이 왜곡되지 않도록 상위 절반만 사용)
    """
    KST = timezone(timedelta(hours=9))
    today = datetime.now(KST).date()

    # 기준선: 최근 안정 구간에서 데이터가 있는 날만 수집 → 상위 절반의 중앙값
    baseline_vals = []
    for i in range(BASELINE_SKIP_DAYS + 1, BASELINE_DAYS + 1):
        d = str(today - timedelta(days=i))
        cnt = daily_counts.get(d, 0)
        if cnt > 0:  # 실제 수집된 날만 기준선에 포함
            baseline_vals.append(cnt)

    if len(baseline_vals) < 3:
        print(f"  [{gallery_name}] 기준선 데이터 부족 — 갭 검사 생략")
        return []

    baseline_vals.sort()
    # 상위 절반만 사용해 이상치(수집 실패일)가 기준선을 낮추는 것 방지
    upper_half = baseline_vals[len(baseline_vals) // 2:]
    median = upper_half[len(upper_half) // 2]
    threshold = max(median * GAP_THRESHOLD, GAP_MIN_POSTS)

    print(f"  [{gallery_name}] 기준 상위중앙값 {median}건/일 → 갭 임계값 {threshold:.0f}건")

    gaps = []
    for i in range(1, GAP_DAYS_BACK + 1):  # 오늘(i=0) 제외
        d = str(today - timedelta(days=i))
        count = daily_counts.get(d, 0)
        if count < threshold:
            gaps.append(d)
            status = "없음" if count == 0 else f"{count}건"
            print(f"  [{gallery_name}] 🕳  갭 탐지: {d} ({status})")

    return sorted(gaps)  # 오래된 날짜 → 최신 날짜 순


# ── Phase 1: 목록 스캔 (메타데이터만, 빠름) ──────────────────────

def scan_gap_metadata(gallery_id, gap_dates, existing_ids, gallery_type, deadline):
    """
    gap_dates 구간의 누락 게시글 메타데이터를 목록 페이지에서 수집.
    본문은 수집하지 않음 (Phase 2에서 async로 일괄 처리).
    """
    url_prefix = get_url_prefix(gallery_type)
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)

    earliest_gap = gap_dates[0]
    gap_date_set = set(gap_dates)
    meta_list = []   # {"id", "title", "writer", "date", "cc", "vc", "rc"}
    page = 1

    print(f"  [{gallery_id}] Phase 1: 목록 스캔 — 갭 날짜 {gap_dates}")

    while page <= MAX_PAGES:
        if datetime.now(KST) >= deadline:
            print(f"  [{gallery_id}] ⏰ 시간 제한 — 목록 스캔 중단 (페이지 {page})")
            break

        url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                print(f"  [{gallery_id}] 페이지 {page} 응답 {r.status_code} — 30초 대기 후 재시도")
                time.sleep(30)
                r = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=REQUEST_TIMEOUT)
                if r.status_code != 200:
                    print(f"  [{gallery_id}] 페이지 {page} 재시도 실패 — 건너뜀")
                    page += 1
                    continue

            soup = BeautifulSoup(r.text, 'html.parser')

            # 소프트 차단 감지
            if is_soft_blocked(soup):
                print(f"  [{gallery_id}] ⚠️  소프트 차단 감지 (페이지 {page}) — 90초 대기 후 재시도")
                time.sleep(90)
                r = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=REQUEST_TIMEOUT)
                soup = BeautifulSoup(r.text, 'html.parser')
                if is_soft_blocked(soup):
                    print(f"  [{gallery_id}] 재시도 후에도 차단 — 백필 중단")
                    break

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
                if not post_id.isdigit() or post_id in existing_ids:
                    continue

                date_str_raw = row.select_one('.gall_date').text.strip()
                date_val = parse_date_str(date_str_raw, now)
                post_date = date_val[:10]

                if post_date < earliest_gap:
                    passed_earliest = True
                    break

                if post_date not in gap_date_set:
                    continue

                writer_elem = row.select_one('.gall_writer')
                writer = (
                    writer_elem['data-nick']
                    if writer_elem and writer_elem.has_attr('data-nick') else ""
                )
                cc, vc, rc = extract_engagement(row)
                meta_list.append({
                    "id": post_id, "title": title_elem.text.strip(),
                    "writer": writer, "date": date_val,
                    "cc": cc, "vc": vc, "rc": rc,
                })
                existing_ids.add(post_id)
                page_new += 1

            if page_new:
                print(f"  [{gallery_id}] 페이지 {page}: {page_new}건 메타 수집 (누적 {len(meta_list)}건)")

            if passed_earliest:
                print(f"  [{gallery_id}] 갭 이전 날짜 도달 — 목록 스캔 완료")
                break

        except Exception as e:
            print(f"  [{gallery_id}] 페이지 {page} 에러: {e}")

        page += 1
        time.sleep(random.uniform(*PAGE_DELAY))

    return meta_list


# ── Phase 2: async 병렬 본문 수집 ────────────────────────────────

async def _fetch_content_one(session, sem, gallery_id, post_id, url_prefix):
    url = (f"https://gall.dcinside.com/{url_prefix}/view/"
           f"?id={gallery_id}&no={post_id}")
    async with sem:
        try:
            await asyncio.sleep(CONTENT_DELAY + random.uniform(0, 0.3))
            async with session.get(
                url, headers=DEFAULT_HEADERS, ssl=False,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as r:
                if r.status == 200:
                    soup = BeautifulSoup(await r.text(), "html.parser")
                    div = soup.select_one(".write_div")
                    return post_id, div.get_text(separator=" ", strip=True) if div else ""
                return post_id, ""
        except Exception:
            return post_id, ""


async def fetch_contents_async(gallery_id, url_prefix, post_ids):
    """post_ids 리스트의 본문을 병렬 수집 → {post_id: content}"""
    sem = asyncio.Semaphore(CONTENT_CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONTENT_CONCURRENCY, ssl=False)
    contents = {}
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            _fetch_content_one(session, sem, gallery_id, pid, url_prefix)
            for pid in post_ids
        ]
        done = 0
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            pid, content = await coro
            contents[pid] = content
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  [{gallery_id}] 본문 수집 중: {done}/{total}건", end="\r")
    print()  # 줄바꿈
    return contents


# ── 시트 저장 ────────────────────────────────────────────────────

def save_to_sheet(sheet, rows):
    for i in range(0, len(rows), BATCH_SIZE):
        sheet.append_rows(rows[i:i + BATCH_SIZE], value_input_option='RAW')
        time.sleep(1.0)


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    KST = timezone(timedelta(hours=9))
    start_time = datetime.now(KST)
    deadline = start_time + timedelta(minutes=MAX_RUNTIME_MIN)

    client = get_gspread_client()
    master_url = os.environ.get('MASTER_SHEET_URL')
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_sheet = client.open_by_url(master_url).sheet1
    gallery_list = [
        {k.strip(): v for k, v in r.items()}
        for r in master_sheet.get_all_records()
    ]

    total_filled = 0

    print(f"\n{'='*60}")
    print(f"  DC-Pickaxe 갭 탐지 + 백필 봇")
    print(f"  실행: {start_time.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  종료 예정: {deadline.strftime('%H:%M')} KST (+{MAX_RUNTIME_MIN}분)")
    print(f"  검사 범위: 최근 {GAP_DAYS_BACK}일 | 임계값: 기준선의 {GAP_THRESHOLD*100:.0f}%")
    print(f"  본문 수집: async {CONTENT_CONCURRENCY}개 동시 (동기 대비 ~{CONTENT_CONCURRENCY*4}배 빠름)")
    print(f"{'='*60}\n")

    for g in gallery_list:
        if datetime.now(KST) >= deadline:
            print("⏰ 전체 시간 제한 도달 — 나머지 갤러리는 다음 실행에 처리됩니다.")
            break

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

            # Phase 1: 목록 스캔 (메타데이터만, 빠름)
            meta_list = scan_gap_metadata(
                gallery_id, gap_dates, existing_ids, gallery_type, deadline
            )

            if not meta_list:
                print(f"  [{gallery_name}] 갭 탐지됐으나 새 글 없음 (이미 수집됐거나 실제 비활성)\n")
                continue

            # Phase 2: async 병렬 본문 수집
            url_prefix = get_url_prefix(gallery_type)
            print(f"  [{gallery_name}] Phase 2: 본문 async 수집 ({len(meta_list)}건)...")
            post_ids = [p["id"] for p in meta_list]
            contents = asyncio.run(
                fetch_contents_async(gallery_id, url_prefix, post_ids)
            )

            # Phase 3: 시트 저장용 rows 조합
            rows = []
            for p in meta_list:
                post_link = (
                    f"https://gall.dcinside.com/{url_prefix}/view/"
                    f"?id={gallery_id}&no={p['id']}"
                )
                rows.append([
                    p["id"], p["title"], contents.get(p["id"], ""),
                    p["writer"], p["date"], post_link,
                    p["cc"], p["vc"], p["rc"],
                ])

            save_to_sheet(sheet, rows)
            total_filled += len(rows)
            print(f"  [{gallery_name}] ✅ {len(rows)}건 보충 완료\n")

        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}\n")

        time.sleep(random.uniform(3.0, 5.0))

    elapsed = int((datetime.now(KST) - start_time).total_seconds() / 60)
    print(f"{'='*60}")
    print(f"  완료! 총 {total_filled}건 보충 | 소요: {elapsed}분")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

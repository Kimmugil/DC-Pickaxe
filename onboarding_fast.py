"""
DC-Pickaxe 온보딩 스크래퍼 (고속 버전)
- Phase 1: 목록 페이지 순차 수집 (재시도 포함) → post ID + 메타데이터
- Phase 2: 본문 async 병렬 수집 (동시 최대 CONTENT_CONCURRENCY개)
- Phase 3: BATCH_SIZE건씩 묶어서 Google Sheets에 저장
- 체크포인트(JSON) 저장으로 중단 후 재개 가능
- --skip-content 플래그로 본문 수집 생략 가능 (초고속)

설치: pip install aiohttp
실행: python onboarding_fast.py
      python onboarding_fast.py --skip-content   ← 본문 생략 모드
"""
import os
import sys
import json
import time
import random
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from utils import (
    get_gspread_client, get_url_prefix,
    parse_date_str, extract_engagement, DEFAULT_HEADERS
)

load_dotenv()

# ── 속도/안전 설정 ─────────────────────────────────────────────
CONTENT_CONCURRENCY = 5    # 본문 동시 요청 수 (높이면 차단 위험)
BATCH_SIZE          = 50   # Google Sheets 배치 저장 단위
LIST_DELAY          = 1.0  # 목록 페이지 요청 간 딜레이(초) — 순차라 서버 부담 낮음
CONTENT_DELAY       = 0.5  # 본문 요청 간 딜레이(초, 세마포어와 함께 적용)
REQUEST_TIMEOUT     = 12   # 요청 타임아웃(초)
MAX_RETRY           = 3    # 500 에러 시 최대 재시도 횟수
RETRY_WAIT          = 5    # 재시도 대기(초, 지수 백오프 기준)
MAX_EMPTY_PAGES     = 5    # 연속 빈 페이지 이 수 이상이면 수집 완료로 판단
# ──────────────────────────────────────────────────────────────

CHECKPOINT_DIR = Path("checkpoints")
CHECKPOINT_DIR.mkdir(exist_ok=True)

SKIP_CONTENT = "--skip-content" in sys.argv


# ── 체크포인트 ─────────────────────────────────────────────────
def ckpt_path(gallery_id):
    return CHECKPOINT_DIR / f"{gallery_id}_fast.json"

def load_checkpoint(gallery_id):
    p = ckpt_path(gallery_id)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collected_ids": [], "last_page": 0}

def save_checkpoint(gallery_id, collected_ids, last_page):
    p = ckpt_path(gallery_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"collected_ids": list(collected_ids), "last_page": last_page}, f, ensure_ascii=False)


# ── 목록 페이지 파싱 ───────────────────────────────────────────
def parse_list_page(html, now, today, existing_ids):
    """
    목록 HTML → (new_posts, already_count, today_count, is_dom_empty)
    - new_posts      : 새로 수집할 게시글 메타데이터 리스트
    - already_count  : 이미 existing_ids에 있어 건너뛴 글 수
    - today_count    : 오늘 글이라 건너뛴 수
    - is_dom_empty   : .us-post 자체가 없으면 True (갤러리 끝)
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".us-post")
    if not rows:
        return [], 0, 0, True

    new_posts = []
    already_count = 0
    today_count = 0

    for row in rows:
        gall_num_elem = row.select_one(".gall_num")
        gall_num_text = gall_num_elem.text.strip() if gall_num_elem else ""
        gall_subject_elem = row.select_one(".gall_subject")
        gall_subject_text = gall_subject_elem.text.strip() if gall_subject_elem else ""
        is_notice = (
            not gall_num_text.isdigit()
            or "공지" in gall_subject_text
            or row.select_one(".icon_notice") is not None
        )

        title_elem = row.select_one(".gall_tit a:not(.reply_num)")
        if not title_elem:
            continue
        href = title_elem.get("href", "")
        if "no=" not in href:
            continue
        post_id = href.split("no=")[1].split("&")[0]
        if not post_id.isdigit():
            continue

        if post_id in existing_ids:
            already_count += 1
            continue

        date_str = row.select_one(".gall_date").text.strip()
        date_val = parse_date_str(date_str, now)
        post_date = today if ":" in date_str else datetime.strptime(date_val, "%Y-%m-%d").date()

        if not is_notice and post_date >= today:
            today_count += 1
            continue

        writer_elem = row.select_one(".gall_writer")
        writer = writer_elem["data-nick"] if writer_elem and writer_elem.has_attr("data-nick") else ""
        comment_count, view_count, recommend_count = extract_engagement(row)

        new_posts.append({
            "id": post_id,
            "title": title_elem.text.strip(),
            "writer": writer,
            "date": date_val,
            "comment_count": comment_count,
            "view_count": view_count,
            "recommend_count": recommend_count,
        })

    return new_posts, already_count, today_count, False


# ── Phase 1: 목록 페이지 순차 수집 (재시도 포함) ──────────────
def collect_metadata(gallery_id, url_prefix, existing_ids, start_page=1):
    """
    목록 페이지를 순차로 스크래핑해 post 메타데이터 리스트 반환.
    500 에러는 지수 백오프로 최대 MAX_RETRY회 재시도.
    실제 빈 페이지(DOM 없음)가 MAX_EMPTY_PAGES회 연속이면 종료.
    """
    import requests as req

    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    today = now.date()

    all_posts = []
    page = start_page
    consecutive_empty = 0
    last_page_done = start_page - 1

    print(f"  목록 수집 시작 (페이지 {start_page}~, 페이지당 딜레이 {LIST_DELAY}s)")

    while True:
        url = f"https://gall.dcinside.com/{url_prefix}/lists/?id={gallery_id}&page={page}"
        html = None

        # 재시도 루프 (500 에러 대응)
        for attempt in range(1, MAX_RETRY + 1):
            try:
                r = req.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=REQUEST_TIMEOUT)
                if r.status_code == 200:
                    html = r.text
                    break
                else:
                    wait = RETRY_WAIT * attempt
                    print(f"  ⚠️  페이지 {page} HTTP {r.status_code} "
                          f"— {wait}초 후 재시도 ({attempt}/{MAX_RETRY})")
                    time.sleep(wait)
            except Exception as e:
                wait = RETRY_WAIT * attempt
                print(f"  ⚠️  페이지 {page} 오류({e}) — {wait}초 후 재시도 ({attempt}/{MAX_RETRY})")
                time.sleep(wait)

        if html is None:
            print(f"  ✗  페이지 {page} {MAX_RETRY}회 재시도 실패 — 건너뜀")
            # 실패는 empty로 카운트하지 않음. 그냥 다음 페이지로.
            page += 1
            time.sleep(LIST_DELAY * 2)
            continue

        new_posts, already_count, today_count, is_dom_empty = parse_list_page(html, now, today, existing_ids)

        if is_dom_empty:
            consecutive_empty += 1
            print(f"  [페이지 {page}] 게시글 DOM 없음 "
                  f"({consecutive_empty}/{MAX_EMPTY_PAGES} 연속 빈 페이지)")
            if consecutive_empty >= MAX_EMPTY_PAGES:
                print(f"\n  갤러리 끝 도달. 목록 수집 완료!")
                break
        else:
            consecutive_empty = 0  # 실제 내용이 있으면 리셋
            all_posts.extend(new_posts)
            last_page_done = page

            parts = []
            if new_posts:
                parts.append(f"신규 {len(new_posts)}건")
            if already_count:
                parts.append(f"기수집 {already_count}건 건너뜀")
            if today_count:
                parts.append(f"오늘 글 {today_count}건 건너뜀")
            summary = " | ".join(parts) if parts else "모두 건너뜀"
            print(f"  [페이지 {page}] {summary}  (누적 {len(all_posts):,}건)")

        page += 1
        time.sleep(LIST_DELAY + random.uniform(0, 0.5))

    print(f"\n  목록 수집 완료: 총 {len(all_posts):,}건 메타데이터")
    return all_posts, last_page_done


# ── Phase 2: 본문 async 병렬 수집 ─────────────────────────────
async def fetch_content(session, sem, gallery_id, post_id, url_prefix):
    url = f"https://gall.dcinside.com/{url_prefix}/view/?id={gallery_id}&no={post_id}"
    async with sem:
        try:
            await asyncio.sleep(CONTENT_DELAY + random.uniform(0, 0.3))
            async with session.get(url, headers=DEFAULT_HEADERS, ssl=False,
                                   timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as r:
                if r.status == 200:
                    html = await r.text()
                    soup = BeautifulSoup(html, "html.parser")
                    div = soup.select_one(".write_div")
                    return post_id, div.get_text(separator=" ", strip=True) if div else ""
                return post_id, ""
        except Exception:
            return post_id, ""


async def collect_contents(gallery_id, url_prefix, post_ids):
    """본문을 병렬로 수집해 {post_id: content} 딕셔너리 반환"""
    sem = asyncio.Semaphore(CONTENT_CONCURRENCY)
    contents = {}
    total = len(post_ids)
    done = 0

    connector = aiohttp.TCPConnector(limit=CONTENT_CONCURRENCY, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_content(session, sem, gallery_id, pid, url_prefix) for pid in post_ids]
        for coro in asyncio.as_completed(tasks):
            pid, content = await coro
            contents[pid] = content
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  본문 수집 중: {done:,}/{total:,}", end="\r")

    print()
    return contents


# ── Phase 3: Google Sheets 배치 저장 ──────────────────────────
def save_to_sheet(sheet, posts_data, gallery_id, url_prefix):
    """BATCH_SIZE씩 나눠 Google Sheets에 저장"""
    total = len(posts_data)
    saved = 0
    for i in range(0, total, BATCH_SIZE):
        batch = posts_data[i:i + BATCH_SIZE]
        rows = []
        for p in batch:
            post_link = (f"https://gall.dcinside.com/{url_prefix}/view/"
                         f"?id={gallery_id}&no={p['id']}")
            rows.append([
                p["id"], p["title"], p.get("content", ""), p["writer"], p["date"],
                post_link, p["comment_count"], p["view_count"], p["recommend_count"]
            ])
        sheet.append_rows(rows, value_input_option="RAW")
        saved += len(rows)
        print(f"  시트 저장: {saved:,}/{total:,}건")
        time.sleep(1.0)  # Sheets API 쿼터 보호


# ── 메인 ───────────────────────────────────────────────────────
async def async_main():
    client = get_gspread_client()
    master_url = os.environ.get("MASTER_SHEET_URL")
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_sheet = client.open_by_url(master_url).sheet1
    raw = master_sheet.get_all_records()
    gallery_list = [{k.strip(): v for k, v in r.items()} for r in raw]

    print("\n=== DC-Pickaxe 온보딩 (고속) — 갤러리 선택 ===")
    for i, g in enumerate(gallery_list):
        print(f"  [{i}] {g.get('갤러리명','이름없음')} "
              f"({g.get('갤러리ID','?')} / {g.get('갤러리타입','마이너')})")

    choice = int(input("\n수집할 갤러리 번호: "))
    selected = gallery_list[choice]

    gallery_id   = selected["갤러리ID"]
    sheet_url    = selected["저장시트 URL"]
    gallery_type = selected.get("갤러리타입", "마이너").strip()
    url_prefix   = get_url_prefix(gallery_type)

    sheet = client.open_by_url(sheet_url).sheet1
    existing_ids = set(v for v in sheet.col_values(1) if str(v).isdigit())

    # 체크포인트 확인
    ckpt = load_checkpoint(gallery_id)
    resume_page = ckpt["last_page"] + 1 if ckpt["last_page"] > 0 else 1
    checkpoint_ids = set(ckpt["collected_ids"])
    existing_ids |= checkpoint_ids

    print(f"\n{'='*55}")
    print(f"  ⚡ DC-Pickaxe 온보딩 스크래퍼 (고속)")
    print(f"{'='*55}")
    print(f"  갤러리  : {selected.get('갤러리명')} ({gallery_id})")
    print(f"  기수집  : {len(existing_ids):,}개 제외")
    print(f"  시작 페이지: {resume_page}")
    print(f"  본문 수집: {'생략 (--skip-content)' if SKIP_CONTENT else f'async 동시 {CONTENT_CONCURRENCY}개'}")
    print(f"  시트 저장: {BATCH_SIZE}건 배치")
    print(f"{'='*55}\n")

    t0 = time.time()

    # Phase 1: 메타데이터 수집 (동기 순차, 재시도 포함)
    print("─── Phase 1: 목록 수집 ───────────────────────────────")
    all_posts, last_page = collect_metadata(gallery_id, url_prefix, existing_ids, resume_page)

    if not all_posts:
        print("  새로 수집할 게시글이 없습니다.")
        return

    # Phase 2: 본문 수집 (async 병렬)
    if not SKIP_CONTENT:
        print(f"\n─── Phase 2: 본문 수집 ({len(all_posts):,}건) ──────────────────")
        post_ids = [p["id"] for p in all_posts]
        contents = await collect_contents(gallery_id, url_prefix, post_ids)
        for p in all_posts:
            p["content"] = contents.get(p["id"], "")
    else:
        print("\n  본문 수집 생략 (--skip-content)")
        for p in all_posts:
            p["content"] = ""

    # Phase 3: 시트 저장
    print(f"\n─── Phase 3: 시트 저장 ({len(all_posts):,}건) ──────────────────")
    save_to_sheet(sheet, all_posts, gallery_id, url_prefix)

    # 체크포인트 갱신
    new_ids = set(p["id"] for p in all_posts)
    save_checkpoint(gallery_id, checkpoint_ids | new_ids, last_page)

    elapsed = time.time() - t0
    mins, secs = divmod(int(elapsed), 60)
    print(f"\n{'='*55}")
    print(f"  완료! {len(all_posts):,}건 저장 | 소요: {mins}분 {secs}초")
    print(f"{'='*55}\n")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n\n  중단됨 (Ctrl+C). checkpoints/ 폴더에 진행상황이 저장됐습니다.")


if __name__ == "__main__":
    main()

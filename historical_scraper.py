"""
DC-Pickaxe 자동 역사 수집 봇 (Historical Scraper)

매일 자동 실행되어 각 갤러리의 과거 게시글을 순차적으로 역방향 수집.
Google Sheets "checkpoints" 탭에 진행상황 저장 → 중단/재시작 지원.
모든 갤러리 수집 완료 시 자동으로 조기 종료 (Actions 분 낭비 방지).

실행: python historical_scraper.py
      python historical_scraper.py --skip-content   (본문 생략, 2~3배 빠름)
"""
import os
import sys
import time
import random
import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import (
    get_gspread_client, get_url_prefix, get_post_content,
    parse_date_str, extract_engagement, DEFAULT_HEADERS,
)

load_dotenv()

# ── 설정 ────────────────────────────────────────────────────────
MAX_RUNTIME_MIN     = 90    # 1회 실행 최대 시간 (분) — 여유있게 조정 가능
CONTENT_CONCURRENCY = 5     # 본문 async 동시 수집 수
CONTENT_DELAY       = 0.5   # 본문 요청 간 딜레이 (초)
PAGE_DELAY          = (1.5, 2.5)   # 목록 페이지 간 딜레이 (초)
BATCH_SIZE          = 50    # 이 건수마다 시트 저장 + 체크포인트 갱신
MAX_EMPTY_PAGES     = 5     # 연속 빈 페이지 이 수 이상 → 해당 갤러리 완료
REQUEST_TIMEOUT     = 12
CHECKPOINT_TAB      = "checkpoints"  # 마스터시트 체크포인트 탭 이름
# ────────────────────────────────────────────────────────────────

SKIP_CONTENT = "--skip-content" in sys.argv


# ── 체크포인트 (Google Sheets) ────────────────────────────────────

def load_checkpoints(master_wb):
    """
    마스터시트 "checkpoints" 탭 로드 또는 신규 생성.
    반환: (worksheet, {gallery_id: {last_page, done, sheet_row}})
    """
    try:
        ws = master_wb.worksheet(CHECKPOINT_TAB)
    except Exception:
        ws = master_wb.add_worksheet(title=CHECKPOINT_TAB, rows=200, cols=5)
        ws.append_row(["갤러리ID", "마지막페이지", "완료여부", "마지막실행", "누적수집"])
        print(f"  '{CHECKPOINT_TAB}' 탭 신규 생성됨")

    checkpoints = {}
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):  # 헤더 제외, 2행부터
        gid = str(row[0]).strip() if row else ""
        if not gid:
            continue
        checkpoints[gid] = {
            "last_page":  int(row[1]) if len(row) > 1 and str(row[1]).isdigit() else 0,
            "done":       str(row[2]).strip().upper() == "TRUE" if len(row) > 2 else False,
            "total":      int(row[4]) if len(row) > 4 and str(row[4]).isdigit() else 0,
            "sheet_row":  i,
        }
    return ws, checkpoints


def save_checkpoint(ckpt_ws, checkpoints, gallery_id, last_page, done, total_saved):
    """갤러리 진행상황을 체크포인트 탭에 저장"""
    KST = timezone(timedelta(hours=9))
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    done_str = "TRUE" if done else "FALSE"

    if gallery_id in checkpoints:
        row_idx = checkpoints[gallery_id]["sheet_row"]
        ckpt_ws.update(
            f"B{row_idx}:E{row_idx}",
            [[last_page, done_str, now_str, total_saved]],
        )
        checkpoints[gallery_id]["last_page"] = last_page
        checkpoints[gallery_id]["done"] = done
        checkpoints[gallery_id]["total"] = total_saved
    else:
        ckpt_ws.append_row([gallery_id, last_page, done_str, now_str, total_saved])
        # 방금 추가한 행의 인덱스 파악
        all_vals = ckpt_ws.get_all_values()
        for i, row in enumerate(all_vals, start=1):
            if row and str(row[0]).strip() == gallery_id:
                row_idx = i
        checkpoints[gallery_id] = {
            "last_page": last_page,
            "done": done,
            "total": total_saved,
            "sheet_row": row_idx,
        }


# ── 본문 async 수집 ───────────────────────────────────────────────

async def _fetch_one(session, sem, gallery_id, post_id, url_prefix):
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
        tasks = [_fetch_one(session, sem, gallery_id, pid, url_prefix) for pid in post_ids]
        for coro in asyncio.as_completed(tasks):
            pid, content = await coro
            contents[pid] = content
    return contents


# ── 시트 저장 ────────────────────────────────────────────────────

def flush_batch(sheet, batch, gallery_id, url_prefix):
    """배치를 Google Sheets에 저장"""
    rows = []
    for p in batch:
        post_link = (f"https://gall.dcinside.com/{url_prefix}/view/"
                     f"?id={gallery_id}&no={p['id']}")
        rows.append([
            p["id"], p["title"], p.get("content", ""), p["writer"], p["date"],
            post_link, p["comment_count"], p["view_count"], p["recommend_count"],
        ])
    sheet.append_rows(rows, value_input_option="RAW")
    time.sleep(1.0)


# ── 갤러리 수집 메인 루프 ─────────────────────────────────────────

def scrape_gallery_historical(
    gallery_id, gallery_type, sheet, existing_ids,
    start_page, ckpt_ws, checkpoints, deadline,
):
    """
    start_page부터 역방향으로 수집. deadline 도달 또는 갤러리 끝이면 종료.
    반환: (total_saved, is_complete)
    """
    url_prefix = get_url_prefix(gallery_type)
    KST = timezone(timedelta(hours=9))
    now_ref = datetime.now(KST)

    page = max(start_page, 1)
    consecutive_empty = 0
    pending = []   # 본문 수집 대기 중인 메타데이터
    total_saved = checkpoints.get(gallery_id, {}).get("total", 0)

    print(f"  [{gallery_id}] 페이지 {page}부터 수집 시작"
          f"{' (본문 생략)' if SKIP_CONTENT else ''}")

    while True:
        # ── 시간 제한 체크 ──────────────────────────────────────
        if datetime.now(KST) >= deadline:
            print(f"  [{gallery_id}] ⏰ 시간 제한 — 페이지 {page}에서 중단")
            if pending:
                if not SKIP_CONTENT:
                    contents = asyncio.run(
                        fetch_contents_async(gallery_id, url_prefix, [p["id"] for p in pending])
                    )
                    for p in pending:
                        p["content"] = contents.get(p["id"], "")
                flush_batch(sheet, pending, gallery_id, url_prefix)
                total_saved += len(pending)
                pending = []
            save_checkpoint(ckpt_ws, checkpoints, gallery_id, page, done=False, total_saved=total_saved)
            return total_saved, False

        # ── 목록 페이지 요청 ────────────────────────────────────
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
                    time.sleep(random.uniform(*PAGE_DELAY))
                    continue

            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select(".us-post")

            if not rows:
                consecutive_empty += 1
                if consecutive_empty >= MAX_EMPTY_PAGES:
                    print(f"  [{gallery_id}] 갤러리 끝 도달 — 수집 완료!")
                    break
                page += 1
                continue

            consecutive_empty = 0
            new_on_page = 0

            for row in rows:
                gall_num_elem = row.select_one(".gall_num")
                gall_num_text = gall_num_elem.text.strip() if gall_num_elem else ""
                is_notice = (
                    not gall_num_text.isdigit()
                    or row.select_one(".icon_notice") is not None
                )
                if is_notice:
                    continue

                title_elem = row.select_one(".gall_tit a:not(.reply_num)")
                if not title_elem:
                    continue
                href = title_elem.get("href", "")
                if "no=" not in href:
                    continue
                post_id = href.split("no=")[1].split("&")[0]
                if not post_id.isdigit() or post_id in existing_ids:
                    continue

                date_str_raw = row.select_one(".gall_date").text.strip()
                date_val = parse_date_str(date_str_raw, now_ref)
                writer_elem = row.select_one(".gall_writer")
                writer = (
                    writer_elem["data-nick"]
                    if writer_elem and writer_elem.has_attr("data-nick") else ""
                )
                cc, vc, rc = extract_engagement(row)

                pending.append({
                    "id": post_id, "title": title_elem.text.strip(),
                    "writer": writer, "date": date_val,
                    "comment_count": cc, "view_count": vc, "recommend_count": rc,
                })
                existing_ids.add(post_id)
                new_on_page += 1

            if new_on_page:
                print(f"  [{gallery_id}] 페이지 {page}: {new_on_page}건"
                      f" (배치 {len(pending)}/{BATCH_SIZE}건)")

        except Exception as e:
            print(f"  [{gallery_id}] 페이지 {page} 에러: {e}")
            page += 1
            time.sleep(random.uniform(*PAGE_DELAY))
            continue

        # ── 배치 저장 ──────────────────────────────────────────
        if len(pending) >= BATCH_SIZE:
            if not SKIP_CONTENT:
                print(f"  [{gallery_id}] 본문 수집 중 ({len(pending)}건)...", end="\r")
                contents = asyncio.run(
                    fetch_contents_async(gallery_id, url_prefix, [p["id"] for p in pending])
                )
                for p in pending:
                    p["content"] = contents.get(p["id"], "")
            flush_batch(sheet, pending, gallery_id, url_prefix)
            total_saved += len(pending)
            pending = []
            save_checkpoint(ckpt_ws, checkpoints, gallery_id, page, done=False, total_saved=total_saved)
            print(f"  [{gallery_id}] 저장 완료 누적 {total_saved:,}건 (페이지 {page})")

        page += 1
        time.sleep(random.uniform(*PAGE_DELAY))

    # ── 갤러리 완료: 잔여 배치 처리 ───────────────────────────
    if pending:
        if not SKIP_CONTENT:
            contents = asyncio.run(
                fetch_contents_async(gallery_id, url_prefix, [p["id"] for p in pending])
            )
            for p in pending:
                p["content"] = contents.get(p["id"], "")
        flush_batch(sheet, pending, gallery_id, url_prefix)
        total_saved += len(pending)

    save_checkpoint(ckpt_ws, checkpoints, gallery_id, page, done=True, total_saved=total_saved)
    return total_saved, True


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    KST = timezone(timedelta(hours=9))
    start_time = datetime.now(KST)
    deadline = start_time + timedelta(minutes=MAX_RUNTIME_MIN)

    client = get_gspread_client()
    master_url = os.environ.get("MASTER_SHEET_URL")
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_wb = client.open_by_url(master_url)
    master_sheet = master_wb.sheet1
    gallery_list = [
        {k.strip(): v for k, v in r.items()}
        for r in master_sheet.get_all_records()
    ]

    ckpt_ws, checkpoints = load_checkpoints(master_wb)

    print(f"\n{'='*60}")
    print(f"  DC-Pickaxe 자동 역사 수집 봇")
    print(f"  실행: {start_time.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  종료 예정: {deadline.strftime('%H:%M')} KST (+{MAX_RUNTIME_MIN}분)")
    print(f"  본문 수집: {'생략 (--skip-content)' if SKIP_CONTENT else f'async 동시 {CONTENT_CONCURRENCY}개'}")
    print(f"{'='*60}\n")

    all_done = True
    grand_total = 0

    for g in gallery_list:
        gallery_id   = g.get("갤러리ID", "").strip()
        gallery_name = g.get("갤러리명", gallery_id)
        sheet_url    = g.get("저장시트 URL", "").strip()
        gallery_type = g.get("갤러리타입", "마이너").strip()

        if not gallery_id or not sheet_url:
            continue

        ckpt = checkpoints.get(gallery_id, {})

        if ckpt.get("done"):
            print(f"── [{gallery_name}] 이미 완료 ✓ (누적 {ckpt.get('total', 0):,}건)")
            continue

        all_done = False
        # 페이지 드리프트 보정: 새 글 추가로 인해 저장된 페이지 번호가 밀릴 수 있어
        # 10페이지 앞에서 다시 시작 (existing_ids로 중복 방지)
        OVERLAP_PAGES = 10
        saved_page = ckpt.get("last_page", 0)
        start_page = max(saved_page - OVERLAP_PAGES + 1, 1) if saved_page > 0 else 1

        overlap_note = f" (드리프트 보정: {saved_page}→{start_page})" if saved_page > 0 else ""
        print(f"\n── [{gallery_name}] 수집 시작 (페이지 {start_page}~){overlap_note}")

        # 시간 제한 사전 체크
        if datetime.now(KST) >= deadline:
            print(f"  시간 초과 — 이번 실행에서는 처리 불가. 다음 실행에 이어서 진행됩니다.")
            all_done = False
            break

        try:
            gsheet = client.open_by_url(sheet_url).sheet1
            existing_ids = set(v for v in gsheet.col_values(1) if str(v).isdigit())

            saved, is_complete = scrape_gallery_historical(
                gallery_id, gallery_type, gsheet, existing_ids,
                start_page, ckpt_ws, checkpoints, deadline,
            )
            grand_total += saved

            if is_complete:
                print(f"  [{gallery_name}] ✅ 완료! 이번 실행 {saved:,}건 수집")
            else:
                print(f"  [{gallery_name}] ⏸ 중단 (시간 제한). 이번 실행 {saved:,}건 수집")
                all_done = False
                break  # 시간 초과 → 나머지 갤러리는 다음 실행으로

        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}")

        time.sleep(random.uniform(3.0, 5.0))

    print(f"\n{'='*60}")
    if all_done:
        print(f"  🎉 모든 갤러리 역사 수집 완료! 이 봇은 더 이상 작업이 없습니다.")
        print(f"     새 갤러리 추가 시 checkpoints 탭에서 해당 갤러리 행 삭제 후 재실행하세요.")
    else:
        print(f"  ⏸  이번 실행 종료. 미완료 갤러리는 다음 실행에서 이어서 진행됩니다.")
    print(f"  이번 실행 총 {grand_total:,}건 수집")
    elapsed = int((datetime.now(KST) - start_time).total_seconds() / 60)
    print(f"  소요 시간: {elapsed}분")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

"""
DC-Pickaxe 체크포인트 리셋 유틸리티

소프트 차단으로 인해 0건 수집 후 done=TRUE로 잘못 마킹된 갤러리를
done=FALSE, last_page=0으로 초기화하여 역사 수집 봇이 재수집하도록 함.

사용법:
  python reset_checkpoints.py                # 0건 수집된 갤러리 전부 리셋
  python reset_checkpoints.py gssc stoneageia guhg 7finger  # 특정 갤러리만
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils import get_gspread_client

load_dotenv()

CHECKPOINT_TAB = "checkpoints"


def main():
    KST = timezone(timedelta(hours=9))
    client = get_gspread_client()

    master_url = os.environ.get("MASTER_SHEET_URL")
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_wb = client.open_by_url(master_url)

    try:
        ckpt_ws = master_wb.worksheet(CHECKPOINT_TAB)
    except Exception:
        print("checkpoints 탭이 없습니다.")
        return

    rows = ckpt_ws.get_all_values()
    if not rows or len(rows) < 2:
        print("체크포인트 데이터가 없습니다.")
        return

    # 커맨드라인으로 특정 갤러리 지정 시 그것만, 아니면 누적수집=0인 것 전부
    target_ids = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    reset_count = 0
    print(f"\n{'='*50}")
    print(f"  DC-Pickaxe 체크포인트 리셋")
    print(f"  실행: {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST")
    print(f"{'='*50}\n")
    print(f"{'갤러리ID':<15} {'마지막페이지':>8} {'완료여부':>8} {'누적수집':>8} {'처리'}")
    print("-" * 55)

    for i, row in enumerate(rows[1:], start=2):
        gid = str(row[0]).strip() if row else ""
        if not gid:
            continue

        last_page = str(row[1]).strip() if len(row) > 1 else "0"
        done = str(row[2]).strip() if len(row) > 2 else ""
        total = str(row[4]).strip() if len(row) > 4 else "0"
        total_int = int(total) if total.isdigit() else 0

        # 리셋 대상 판정
        should_reset = False
        if target_ids:
            should_reset = gid in target_ids
        else:
            # 자동 판정: done=TRUE인데 누적수집이 0이거나 매우 적은 경우
            should_reset = (done.upper() == "TRUE" and total_int == 0)

        action = "✅ 리셋" if should_reset else "  건너뜀"
        print(f"{gid:<15} {last_page:>8} {done:>8} {total_int:>8}건  {action}")

        if should_reset:
            now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            ckpt_ws.update(
                f"B{i}:E{i}",
                [["0", "FALSE", now_str, "0"]],
            )
            reset_count += 1

    print(f"\n총 {reset_count}개 갤러리 체크포인트 리셋 완료.")
    print("다음 historical_scraper 실행 시 해당 갤러리를 처음부터 재수집합니다.\n")


if __name__ == "__main__":
    main()

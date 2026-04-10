"""
DC-Pickaxe 갤러리 시트 중복 제거 유틸리티

동일한 글번호(A열)가 여러 행에 걸쳐 중복 저장된 경우,
첫 번째 등장한 행만 남기고 나머지를 삭제합니다.

사용법:
  python dedup_sheets.py            # 모든 갤러리 시트 정리
  python dedup_sheets.py gssc guhg  # 특정 갤러리만

주의: 시트에서 행을 직접 삭제하므로 실행 전 백업 권장.
"""
import os
import sys
import time
from dotenv import load_dotenv
from utils import get_gspread_client

load_dotenv()

TARGET_IDS = set(sys.argv[1:]) if len(sys.argv) > 1 else None


def dedup_sheet(sheet, gallery_id, gallery_name):
    print(f"  [{gallery_name}] 데이터 로드 중...")
    all_values = sheet.get_all_values()

    if not all_values:
        print(f"  [{gallery_name}] 시트가 비어있음 — 건너뜀")
        return 0

    # 헤더 행 감지: 첫 행이 숫자가 아니면 헤더로 취급
    start_row = 0
    if all_values and not str(all_values[0][0]).isdigit():
        start_row = 1

    seen = {}      # post_id → 처음 등장한 행 번호 (1-indexed, inclusive header)
    dup_rows = []  # 삭제할 행 번호 목록 (내림차순으로 삭제해야 인덱스 밀림 방지)

    for i, row in enumerate(all_values[start_row:], start=start_row + 1):
        post_id = str(row[0]).strip() if row else ""
        if not post_id or not post_id.isdigit():
            continue
        if post_id in seen:
            dup_rows.append(i)
        else:
            seen[post_id] = i

    if not dup_rows:
        print(f"  [{gallery_name}] 중복 없음 ✓ (총 {len(seen)}건)")
        return 0

    print(f"  [{gallery_name}] 중복 {len(dup_rows)}행 삭제 예정 (고유 글번호 {len(seen)}개)")

    # 내림차순으로 삭제 (위에서부터 삭제하면 인덱스가 밀림)
    dup_rows.sort(reverse=True)
    deleted = 0
    for row_idx in dup_rows:
        sheet.delete_rows(row_idx)
        deleted += 1
        time.sleep(0.5)  # API rate limit 방지

    print(f"  [{gallery_name}] ✅ {deleted}행 삭제 완료")
    return deleted


def main():
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

    total_deleted = 0
    print(f"\n{'='*55}")
    print(f"  DC-Pickaxe 갤러리 시트 중복 제거")
    if TARGET_IDS:
        print(f"  대상: {', '.join(TARGET_IDS)}")
    else:
        print(f"  대상: 전체 갤러리")
    print(f"{'='*55}\n")

    for g in gallery_list:
        gallery_id   = str(g.get("갤러리ID", "")).strip()
        gallery_name = g.get("갤러리명", gallery_id)
        sheet_url    = str(g.get("저장시트 URL", "")).strip()

        if not gallery_id or not sheet_url:
            continue
        if TARGET_IDS and gallery_id not in TARGET_IDS:
            continue

        try:
            sheet = client.open_by_url(sheet_url).sheet1
            deleted = dedup_sheet(sheet, gallery_id, gallery_name)
            total_deleted += deleted
        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}")

        time.sleep(2.0)

    print(f"\n총 {total_deleted}행 삭제 완료.\n")


if __name__ == "__main__":
    main()

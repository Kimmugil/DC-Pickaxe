"""
DC-Pickaxe 갤러리 시트 중복 제거 유틸리티

동일한 글번호(A열)가 여러 행에 걸쳐 중복 저장된 경우,
첫 번째 등장한 행만 남기고 나머지를 제거합니다.

방식: 전체 로드 → 메모리 중복 제거 → 시트 초기화 → 재기록
(행 단위 삭제보다 훨씬 빠르고 안정적)

사용법:
  python dedup_sheets.py            # 모든 갤러리 시트 정리
  python dedup_sheets.py gssc guhg  # 특정 갤러리만 (갤러리ID 기준)
"""
import os
import sys
import time
from dotenv import load_dotenv
from utils import get_gspread_client

load_dotenv()

TARGET_IDS = set(sys.argv[1:]) if len(sys.argv) > 1 else None
BATCH_SIZE = 500  # append_rows 배치 크기


def dedup_sheet(sheet, gallery_id, gallery_name):
    print(f"  [{gallery_name}] 데이터 로드 중...")
    all_values = sheet.get_all_values()

    if not all_values:
        print(f"  [{gallery_name}] 시트가 비어있음 — 건너뜀")
        return 0

    # 헤더 행 감지: 첫 행이 숫자가 아니면 헤더로 취급
    header = None
    data_rows = all_values
    if all_values and not str(all_values[0][0]).strip().isdigit():
        header = all_values[0]
        data_rows = all_values[1:]

    # 메모리에서 중복 제거 (첫 번째 등장만 유지)
    seen = set()
    kept = []
    dup_count = 0

    for row in data_rows:
        post_id = str(row[0]).strip() if row else ""
        if not post_id or not post_id.isdigit():
            kept.append(row)  # 비정상 행은 그냥 유지
            continue
        if post_id in seen:
            dup_count += 1
        else:
            seen.add(post_id)
            kept.append(row)

    if dup_count == 0:
        print(f"  [{gallery_name}] 중복 없음 ✓ (총 {len(seen)}건)")
        return 0

    print(f"  [{gallery_name}] {dup_count}건 중복 발견 → 시트 재기록 중 ({len(kept)}건 유지)")

    # 시트 전체 초기화
    sheet.clear()
    time.sleep(1.0)

    # 헤더 먼저 기록 (있는 경우)
    write_rows = []
    if header:
        write_rows.append(header)
    write_rows.extend(kept)

    # 배치로 기록
    for i in range(0, len(write_rows), BATCH_SIZE):
        batch = write_rows[i:i + BATCH_SIZE]
        sheet.append_rows(batch, value_input_option="RAW")
        time.sleep(1.0)

    print(f"  [{gallery_name}] ✅ 중복 {dup_count}건 제거 완료 (최종 {len(kept)}건)")
    return dup_count


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

    total_removed = 0
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
            removed = dedup_sheet(sheet, gallery_id, gallery_name)
            total_removed += removed
        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}")

        time.sleep(2.0)

    print(f"\n총 {total_removed}건 중복 제거 완료.\n")


if __name__ == "__main__":
    main()

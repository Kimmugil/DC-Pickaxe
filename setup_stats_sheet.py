"""
DC-Pickaxe stats 탭 생성 유틸리티

각 갤러리 스프레드시트에 "stats" 탭을 만들고
구글 시트 함수(COUNTIF)로 일자별 게시글 수가 자동 집계되도록 설정.

stats 탭 구조:
  A열: 날짜 (YYYY-MM-DD) — SORT/UNIQUE 함수로 E열에서 자동 추출
  B열: 게시글수 — COUNTIF 함수로 자동 집계

새 데이터가 원본 시트에 추가되면 stats 탭도 자동으로 갱신됨.

사용법:
  python setup_stats_sheet.py          # 전체 갤러리
  python setup_stats_sheet.py gssc     # 특정 갤러리만
"""
import os
import sys
import time
import gspread
from dotenv import load_dotenv
from utils import get_gspread_client

load_dotenv()

TARGET_IDS = set(sys.argv[1:]) if len(sys.argv) > 1 else None
STATS_TAB  = "stats"


def setup_stats(wb, gallery_id, gallery_name):
    data_ws = wb.sheet1
    data_tab = data_ws.title

    # 시트명에 특수문자/공백 있으면 따옴표로 감쌈
    safe = f"'{data_tab}'" if (" " in data_tab or not data_tab.isalnum()) else data_tab

    # 날짜 자동 추출 공식: E열에서 앞 10자리(YYYY-MM-DD)만 추출, 유일값 정렬
    date_formula = (
        f"=IFERROR("
        f"SORT(UNIQUE(FILTER("
        f"ARRAYFORMULA(LEFT({safe}!E2:E,10)),"
        f"LEN({safe}!E2:E)>=10"
        f"))),"
        f'"")'
    )
    # 날짜별 게시글 수: COUNTIF로 "YYYY-MM-DD*" 패턴 매칭 (시간 포함 날짜 모두 커버)
    count_formula = (
        f'=ARRAYFORMULA(IF(A2:A="","",COUNTIF({safe}!E:E,A2:A&"*")))'
    )

    # stats 탭 생성 또는 초기화
    try:
        ws = wb.worksheet(STATS_TAB)
        ws.clear()
        print(f"  [{gallery_name}] 기존 stats 탭 초기화")
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=STATS_TAB, rows=1000, cols=2)
        print(f"  [{gallery_name}] stats 탭 신규 생성")

    time.sleep(1.0)

    # 헤더 + 공식 작성
    ws.update("A1:B1", [["날짜", "게시글수"]], value_input_option="USER_ENTERED")
    time.sleep(0.5)
    ws.update("A2", [[date_formula]],  value_input_option="USER_ENTERED")
    time.sleep(0.5)
    ws.update("B2", [[count_formula]], value_input_option="USER_ENTERED")
    time.sleep(0.5)

    print(f"  [{gallery_name}] ✅ stats 탭 설정 완료 (원본 탭: {data_tab})")


def main():
    client = get_gspread_client()
    master_url = os.environ.get("MASTER_SHEET_URL")
    if not master_url:
        raise ValueError("MASTER_SHEET_URL 환경 변수가 없습니다.")

    master_wb = client.open_by_url(master_url)
    gallery_list = [
        {k.strip(): v for k, v in r.items()}
        for r in master_wb.sheet1.get_all_records()
    ]

    print(f"\n{'='*55}")
    print(f"  DC-Pickaxe stats 탭 설정")
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
            wb = client.open_by_url(sheet_url)
            setup_stats(wb, gallery_id, gallery_name)
        except Exception as e:
            print(f"  [{gallery_name}] 에러: {e}")

        time.sleep(2.0)

    print("\n완료!\n")


if __name__ == "__main__":
    main()

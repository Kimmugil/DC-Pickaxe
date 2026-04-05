"""DC-Pickaxe Data Layer — Google Sheets 연동 + 헬퍼 함수"""
import os
import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 기본 UI 텍스트 (마스터시트 config 탭에서 덮어쓸 수 있음)
_DEFAULT_CONFIG = {
    "app_title":        "DC-Pickaxe 관제탑",
    "app_subtitle":     "디시인사이드 갤러리 자동 수집 모니터링",
    "pm_name":          "김무길",
    "app_version":      "1.0.0",
    "announcement":     "",
    "collection_note":  "봇 실행 시 갱신 (1시간 주기)",
    "sidebar_menu_home":"🏠 메인 대시보드",
}

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ── Google Sheets 클라이언트 ──────────────────────────────────────

@st.cache_resource
def get_client():
    j = os.environ.get("GCP_CREDENTIALS")
    if not j:
        return None
    d = json.loads(j)
    return gspread.authorize(Credentials.from_service_account_info(d, scopes=_SCOPES))


# ── 마스터시트 ────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_master() -> pd.DataFrame | None:
    c = get_client()
    if not c:
        return None
    url = os.environ.get("MASTER_SHEET_URL")
    if not url:
        return None
    recs = c.open_by_url(url).sheet1.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in recs])


# ── Config 탭 (마스터시트 두 번째 탭 이름: "config") ───────────────
# 탭이 없으면 _DEFAULT_CONFIG 그대로 사용
# 탭 구조: A열=key, B열=value

@st.cache_data(ttl=60)
def load_config() -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    c = get_client()
    if not c:
        return cfg
    url = os.environ.get("MASTER_SHEET_URL")
    if not url:
        return cfg
    try:
        wb = c.open_by_url(url)
        ws = None
        # 대소문자 무관하게 탭 탐색
        for name in ["config", "Config", "CONFIG", "설정"]:
            try:
                ws = wb.worksheet(name)
                break
            except Exception:
                continue
        if ws is None:
            return cfg
        for row in ws.get_all_values():
            key = row[0].strip() if row else ""
            # 헤더행("key") 및 빈 키 건너뜀
            if len(row) >= 2 and key and key.lower() != "key":
                cfg[key] = row[1].strip()
    except Exception:
        pass
    return cfg


# ── 갤러리 게시글 수 (빠른 조회) ──────────────────────────────────

@st.cache_data(ttl=300)
def get_count(url: str) -> int:
    c = get_client()
    if not c:
        return -1
    try:
        return sum(1 for v in c.open_by_url(url).sheet1.col_values(1) if str(v).isdigit())
    except Exception:
        return -1


# ── 갤러리 데이터 로드 (내용 열 C 제외) ──────────────────────────

@st.cache_data(ttl=300)
def load_gallery(url: str) -> pd.DataFrame:
    c = get_client()
    if not c:
        return pd.DataFrame()
    try:
        res = c.open_by_url(url).sheet1.batch_get(["A:B", "D:I"])
        ab = res[0] if res else []
        di = res[1] if len(res) > 1 else []
        if not ab:
            return pd.DataFrame()
        rows = []
        for i in range(max(len(ab), len(di))):
            a = list(ab[i]) if i < len(ab) else []
            d = list(di[i]) if i < len(di) else []
            while len(a) < 2:
                a.append("")
            while len(d) < 6:
                d.append("")
            if not str(a[0]).isdigit():
                continue
            rows.append({
                "글번호": a[0], "제목": a[1],
                "작성자": d[0], "날짜":   d[1], "링크": d[2],
                "댓글수": d[3] or "0", "조회수": d[4] or "0", "추천수": d[5] or "0",
            })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["날짜_dt"]   = pd.to_datetime(df["날짜"], errors="coerce")
        df["날짜_date"] = df["날짜_dt"].dt.date
        for col in ["댓글수", "조회수", "추천수"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        return df.sort_values("날짜_dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# ── 인기글 계산 ────────────────────────────────────────────────────

def get_hot_posts(df: pd.DataFrame, n: int = 5) -> tuple:
    """
    최근 24시간 내 인기글 우선 (3개 미만이면 7일로 확장, 그래도 없으면 전체).
    공지글(글번호 비숫자)은 이미 로드 단계에서 제외됨.
    반환: (DataFrame, period_label: str)
    """
    if df.empty:
        return pd.DataFrame(), "전체"
    tmp = df.copy()
    tmp["점수"] = tmp["추천수"] * 2 + tmp["댓글수"]
    cols = ["글번호", "제목", "날짜", "댓글수", "추천수", "링크", "점수"]
    today = datetime.now(KST).date()
    for days, label in [(1, "최근 24시간"), (7, "최근 7일"), (99999, "전체")]:
        pool = tmp[tmp["날짜_date"] >= today - timedelta(days=days)] if days < 99999 else tmp
        if len(pool) >= min(n, 3):
            return pool.nlargest(n, "점수")[cols].reset_index(drop=True), label
    return pd.DataFrame(), "전체"


# ── 컬럼명 탐색 ────────────────────────────────────────────────────

def find_col(df: pd.DataFrame, *keywords) -> str | None:
    for kw in keywords:
        for c in df.columns:
            if kw in c:
                return c
    return None


# ── 시간 ago 표시 ─────────────────────────────────────────────────

def time_ago(s: str) -> str:
    try:
        t = datetime.strptime(str(s).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        m = int((datetime.now(KST) - t).total_seconds() / 60)
        if m < 1:    return "방금 전"
        if m < 60:   return f"{m}분 전"
        if m < 1440: return f"{m // 60}시간 전"
        return f"{m // 1440}일 전"
    except Exception:
        return str(s) or "-"


# ── 상태 배지 HTML ────────────────────────────────────────────────

def bdg(msg: str) -> str:
    m = str(msg).strip()
    if not m:
        return '<span class="bdg bnone">미실행</span>'
    if "에러" in m:
        return '<span class="bdg berr">에러</span>'
    if "새 글 없음" in m:
        return '<span class="bdg bnfo">새 글 없음</span>'
    if "개 수집" in m:
        return f'<span class="bdg bok">{m}</span>'
    return f'<span class="bdg bnone">{m}</span>'

import os
import json
import pandas as pd
import altair as alt
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="DC-Pickaxe 관제탑", page_icon="⛏️", layout="wide")

GALLERY_COLORS = ["#FEE500", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899"]
KST = timezone(timedelta(hours=9))

st.markdown("""
<style>
.stApp,[data-testid="stAppViewContainer"]>.main{background:#f4f6fb!important}
[data-testid="stHeader"]{background:transparent!important;box-shadow:none}
[data-testid="stToolbar"]{display:none}
.block-container{padding:1.4rem 2rem!important;max-width:1280px}

/* 사이드바 */
section[data-testid="stSidebar"]{background:white!important;border-right:1px solid #eef0f5!important}
section[data-testid="stSidebar"] .block-container{padding:0!important;max-width:none!important}
section[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;border:none!important;box-shadow:none!important;
  text-align:left!important;color:#6b7280!important;font-weight:500!important;
  padding:9px 20px!important;border-radius:8px!important;font-size:14px!important;
  width:100%;transition:all .15s!important}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:#f0f4ff!important;color:#3b82f6!important}

/* 카드 */
.card{background:white;border-radius:14px;padding:20px;box-shadow:0 1px 12px rgba(0,0,0,.06);margin-bottom:12px}
.card-title{font-size:14px;font-weight:700;color:#374151;margin:0 0 14px}

/* 메트릭 */
.mcard{background:white;border-radius:14px;padding:18px 14px 14px;text-align:center;box-shadow:0 1px 12px rgba(0,0,0,.06)}
.mval{font-size:26px;font-weight:800;color:#1f2937;line-height:1.2}
.mlbl{font-size:10px;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:.7px;margin-top:4px}

/* 배지 */
.badge{display:inline-block;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:700;white-space:nowrap}
.bs{background:#dcfce7;color:#15803d}
.bi{background:#dbeafe;color:#1d4ed8}
.be{background:#fee2e2;color:#b91c1c}
.bn{background:#f3f4f6;color:#6b7280}

/* 섹션 타이틀 */
.stl{font-size:15px;font-weight:700;color:#1f2937;border-left:4px solid #FEE500;padding-left:10px;margin:18px 0 10px}

/* 테이블 헤더 */
.th{font-size:10px;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:.6px;padding:0 6px;margin-bottom:4px}

/* 행 셀 */
.rc{background:white;border-radius:10px;padding:10px 13px;box-shadow:0 1px 6px rgba(0,0,0,.05);font-size:13px;color:#374151}

.stLinkButton>a{background:#f0f7ff!important;color:#2563eb!important;border:1.5px solid #bfdbfe!important;border-radius:8px!important;font-size:12px!important;font-weight:600!important}
.stLinkButton>a:hover{background:#dbeafe!important}
[data-testid="stExpander"]{background:white!important;border-radius:12px!important;border:1px solid #eef0f5!important}
.vega-embed{background:transparent!important}
</style>
""", unsafe_allow_html=True)


# ── Data ──────────────────────────────────────────────────────

@st.cache_resource
def get_client():
    j = os.environ.get('GCP_CREDENTIALS')
    if not j: return None
    d = json.loads(j)
    sc = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    return gspread.authorize(Credentials.from_service_account_info(d, scopes=sc))

@st.cache_data(ttl=60)
def load_master():
    c = get_client()
    if not c: return None
    url = os.environ.get('MASTER_SHEET_URL')
    if not url: return None
    recs = c.open_by_url(url).sheet1.get_all_records()
    return pd.DataFrame([{k.strip(): v for k, v in r.items()} for r in recs])

@st.cache_data(ttl=300)
def get_count(url: str) -> int:
    c = get_client()
    if not c: return -1
    try:
        vals = c.open_by_url(url).sheet1.col_values(1)
        return sum(1 for v in vals if str(v).isdigit())
    except: return -1

@st.cache_data(ttl=300)
def load_gallery(url: str) -> pd.DataFrame:
    """본문(C컬럼) 제외, A:B + D:I 컬럼만 batch_get으로 로드"""
    c = get_client()
    if not c: return pd.DataFrame()
    try:
        sh = c.open_by_url(url).sheet1
        res = sh.batch_get(['A:B', 'D:I'])
        ab = res[0] if res else []
        di = res[1] if len(res) > 1 else []
        if not ab: return pd.DataFrame()
        rows = []
        for i in range(max(len(ab), len(di))):
            a = list(ab[i]) if i < len(ab) else []
            d = list(di[i]) if i < len(di) else []
            while len(a) < 2: a.append('')
            while len(d) < 6: d.append('')
            if not str(a[0]).isdigit(): continue
            rows.append({'글번호': a[0], '제목': a[1], '작성자': d[0],
                         '날짜': d[1], '링크': d[2],
                         '댓글수': d[3] or '0', '조회수': d[4] or '0', '추천수': d[5] or '0'})
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows)
        df['날짜_dt']   = pd.to_datetime(df['날짜'], errors='coerce')
        df['날짜_date'] = df['날짜_dt'].dt.date
        for col in ['댓글수', '조회수', '추천수']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df.sort_values('날짜_dt').reset_index(drop=True)
    except: return pd.DataFrame()


# ── Helpers ───────────────────────────────────────────────────

def time_ago(s: str) -> str:
    try:
        t = datetime.strptime(str(s).strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        m = int((datetime.now(KST) - t).total_seconds() / 60)
        if m < 1: return "방금 전"
        if m < 60: return f"{m}분 전"
        if m < 1440: return f"{m//60}시간 전"
        return f"{m//1440}일 전"
    except: return str(s) or "-"

def bdg(msg: str) -> str:
    m = str(msg).strip()
    if not m:            return '<span class="badge bn">⚪ 미실행</span>'
    if "에러"    in m:   return f'<span class="badge be">❌ {m}</span>'
    if "새 글 없음" in m: return '<span class="badge bi">✅ 새 글 없음</span>'
    if "개 수집" in m:   return f'<span class="badge bs">🟢 {m}</span>'
    return f'<span class="badge bn">{m}</span>'

def find_col(df, *kws):
    for kw in kws:
        for c in df.columns:
            if kw in c: return c
    return None

def refresh_btn(key="rf"):
    if st.button("🔄 새로고침", use_container_width=True, key=key):
        st.cache_data.clear(); st.rerun()


# ── Main Page ─────────────────────────────────────────────────

def page_main(df, nc, ic, uc, rc, lc, counts):
    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    hc, bc = st.columns([9, 1])
    with hc:
        st.markdown(f"""
        <div style="background:linear-gradient(90deg,#FEE500,#FFD000);border-radius:18px;
             padding:18px 28px;box-shadow:0 6px 20px rgba(254,229,0,.35);
             display:flex;align-items:center;justify-content:space-between;margin-bottom:18px">
          <div>
            <p style="font-size:22px;font-weight:900;color:#111;margin:0">⛏️ DC-Pickaxe 관제탑</p>
            <p style="font-size:12px;color:#555;margin:4px 0 0">디시인사이드 갤러리 자동 수집 모니터링</p>
          </div>
          <div style="text-align:right;font-size:12px;color:#444">
            🕐 현재 시각 (KST)<br><strong>{now}</strong>
          </div>
        </div>""", unsafe_allow_html=True)
    with bc:
        st.markdown("<div style='padding-top:12px'></div>", unsafe_allow_html=True)
        refresh_btn("rf_main")

    total = len(df)
    errs  = sum(1 for v in df[lc] if "에러" in str(v)) if lc else 0
    tp    = sum(v for v in counts.values() if v >= 0)
    lr    = str(df[rc].iloc[0]) if rc else ""

    m1,m2,m3,m4 = st.columns(4)
    for col, top_c, icon, val, lbl in [
        (m1,"#3b82f6","🗂️",f"{total}개","등록 갤러리"),
        (m2,"#10b981","📄",f"{tp:,}건","총 수집 게시글"),
        (m3,"#f59e0b","✅",f"{total-errs}/{total}","정상 갤러리"),
        (m4,"#8b5cf6","🕐",time_ago(lr),"마지막 실행"),
    ]:
        with col:
            st.markdown(f"""<div class="mcard" style="border-top:4px solid {top_c}">
              <div style="font-size:22px;margin-bottom:6px">{icon}</div>
              <div class="mval">{val}</div><div class="mlbl">{lbl}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 차트 2종
    ch1, ch2 = st.columns([3,2])
    with ch1:
        st.markdown('<div class="card"><p class="card-title">갤러리별 수집 게시글 수</p>', unsafe_allow_html=True)
        if counts:
            bdf = pd.DataFrame([{'갤러리':k,'수':max(v,0)} for k,v in counts.items()]).sort_values('수',ascending=False)
            st.altair_chart(
                alt.Chart(bdf).mark_bar(cornerRadiusTopLeft=4,cornerRadiusTopRight=4)
                .encode(x=alt.X('갤러리:N',sort=None,title='',axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('수:Q',title='',axis=alt.Axis(format=',d')),
                        color=alt.Color('갤러리:N',scale=alt.Scale(scheme='tableau10'),legend=None),
                        tooltip=[alt.Tooltip('갤러리:N'),alt.Tooltip('수:Q',title='게시글수',format=',')])
                .properties(height=200).configure_view(strokeWidth=0)
                .configure_axis(grid=True,gridColor='#f5f5f5'),
                use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with ch2:
        st.markdown('<div class="card"><p class="card-title">수집 상태 분포</p>', unsafe_allow_html=True)
        if lc:
            sm = {'수집성공':0,'새글없음':0,'에러':0,'미실행':0}
            for v in df[lc]:
                s=str(v)
                if '개 수집' in s: sm['수집성공']+=1
                elif '새 글 없음' in s: sm['새글없음']+=1
                elif '에러' in s: sm['에러']+=1
                else: sm['미실행']+=1
            pdf = pd.DataFrame([{'상태':k,'수':v} for k,v in sm.items() if v>0])
            st.altair_chart(
                alt.Chart(pdf).mark_arc(innerRadius=50,outerRadius=85)
                .encode(theta=alt.Theta('수:Q'),
                        color=alt.Color('상태:N',
                          scale=alt.Scale(domain=['수집성공','새글없음','에러','미실행'],
                                          range=['#22c55e','#3b82f6','#ef4444','#d1d5db']),
                          legend=alt.Legend(orient='bottom',labelFontSize=12)),
                        tooltip=['상태:N','수:Q'])
                .properties(height=200).configure_view(strokeWidth=0),
                use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 갤러리 현황 테이블
    st.markdown('<p class="stl">📋 갤러리별 수집 현황</p>', unsafe_allow_html=True)
    hcols = st.columns([3,2.5,2,2,1.6])
    for c,t in zip(hcols,["갤러리","수집 상태","총 게시글","마지막 실행","바로가기"]):
        c.markdown(f"<p class='th'>{t}</p>", unsafe_allow_html=True)

    for i,(_, row) in enumerate(df.iterrows()):
        color = GALLERY_COLORS[i % len(GALLERY_COLORS)]
        gn = str(row.get(nc,''));  gi = str(row.get(ic,'')) if ic else ''
        rm = str(row.get(lc,'')) if lc else '';  lr2 = str(row.get(rc,'')) if rc else ''
        su = str(row.get(uc,'')) if uc else '';  cnt = counts.get(gn,-1)
        c1,c2,c3,c4,c5 = st.columns([3,2.5,2,2,1.6])
        with c1:
            st.markdown(f"""<div class="rc" style="border-left:5px solid {color};border-radius:0 10px 10px 0">
              <div style="font-weight:700;font-size:14px;color:#1f2937">{gn}</div>
              <div style="font-size:11px;color:#9ca3af">{gi}</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="rc">{bdg(rm)}</div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="rc" style="font-weight:700">📄 {f"{cnt:,}건" if cnt>=0 else "집계 중"}</div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="rc" style="color:#6b7280">🕐 {time_ago(lr2)}</div>', unsafe_allow_html=True)
        with c5:
            if su.startswith('http'): st.link_button("열기 →", su, use_container_width=True)
        st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

    st.markdown("<p style='text-align:right;font-size:11px;color:#9ca3af'>💡 총 게시글 수는 5분 주기 갱신</p>", unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("📚 온보딩(과거 데이터) 스크래퍼 실행 가이드"):
        st.markdown("""
온보딩 스크래퍼는 **반드시 로컬 PC에서 실행**해야 합니다. 어제부터 역방향으로 수집하며 **Ctrl+C로 언제든 중단**해도 저장된 데이터는 보존됩니다.

1. `git clone [깃허브 주소]` 로 코드 다운로드
2. `.env` 파일 생성 후 입력:
   ```
   GCP_CREDENTIALS={...서비스계정 JSON...}
   MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/...
   ```
3. `pip install -r requirements.txt`
4. `python onboarding_scraper.py` 실행 → 갤러리 선택
        """)
    st.markdown("<p style='text-align:right;color:#9ca3af;font-size:11px'>시스템 총괄 PM : 김무길 | DC-Pickaxe v2.1</p>", unsafe_allow_html=True)


# ── Gallery Detail Page ───────────────────────────────────────

def page_gallery(row, nc, ic, uc, rc, lc):
    gn = str(row.get(nc,''));  gi = str(row.get(ic,'')) if ic else ''
    su = str(row.get(uc,'')) if uc else '';  lr = str(row.get(rc,'')) if rc else ''
    rm = str(row.get(lc,'')) if lc else ''

    hc, bc = st.columns([9,1])
    with hc:
        st.markdown(f"""
        <div style="background:white;border-radius:16px;padding:16px 24px;
             box-shadow:0 2px 14px rgba(0,0,0,.06);border-left:5px solid #FEE500;margin-bottom:18px">
          <p style="font-size:20px;font-weight:900;color:#1f2937;margin:0">📊 {gn}</p>
          <p style="font-size:12px;color:#9ca3af;margin:4px 0 0">
            ID: {gi} &nbsp;|&nbsp; 최근 수집: {time_ago(lr)} &nbsp;|&nbsp; {bdg(rm)}
          </p>
        </div>""", unsafe_allow_html=True)
    with bc:
        st.markdown("<div style='padding-top:12px'></div>", unsafe_allow_html=True)
        refresh_btn("rf_gall")

    with st.spinner("갤러리 데이터 로딩 중... (최초 1회)"):
        gdf = load_gallery(su)

    if gdf.empty:
        st.info("수집된 게시글이 없습니다. 온보딩 스크래퍼를 실행해주세요.")
        return

    total = len(gdf)
    vd = gdf['날짜_date'].dropna()
    dmin = vd.min() if len(vd) else None
    dmax = vd.max() if len(vd) else None
    days = max((dmax - dmin).days + 1, 1) if dmin and dmax else 1
    avg  = round(total / days, 1)

    # 메트릭
    m1,m2,m3,m4 = st.columns(4)
    for col, top_c, icon, val, lbl in [
        (m1,"#3b82f6","📄",f"{total:,}건","총 수집 게시글"),
        (m2,"#10b981","📅",str(dmin) if dmin else "-","최초 수집 날짜"),
        (m3,"#f59e0b","🗓️",str(dmax) if dmax else "-","최근 수집 날짜"),
        (m4,"#8b5cf6","📈",f"{avg}건/일","일평균 게시글"),
    ]:
        with col:
            st.markdown(f"""<div class="mcard" style="border-top:4px solid {top_c}">
              <div style="font-size:20px;margin-bottom:6px">{icon}</div>
              <div class="mval" style="font-size:20px">{val}</div>
              <div class="mlbl">{lbl}</div></div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 일별 게시글 수 (최근 60일)
    st.markdown('<div class="card"><p class="card-title">📅 일별 게시글 수 (최근 60일)</p>', unsafe_allow_html=True)
    daily = (gdf.groupby('날짜_date').size().reset_index(name='게시글수')
             .rename(columns={'날짜_date':'날짜'}).sort_values('날짜').tail(60))
    daily['날짜'] = pd.to_datetime(daily['날짜'])
    st.altair_chart(
        alt.Chart(daily).mark_bar(color='#FEE500',cornerRadiusTopLeft=3,cornerRadiusTopRight=3)
        .encode(x=alt.X('날짜:T',title='',axis=alt.Axis(format='%m/%d',labelAngle=-30)),
                y=alt.Y('게시글수:Q',title='',axis=alt.Axis(format=',d')),
                tooltip=[alt.Tooltip('날짜:T',format='%Y-%m-%d'),alt.Tooltip('게시글수:Q',format=',')])
        .properties(height=220).configure_view(strokeWidth=0)
        .configure_axis(grid=True,gridColor='#f5f5f5'),
        use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 누적 추이
    st.markdown('<div class="card"><p class="card-title">📈 누적 게시글 추이</p>', unsafe_allow_html=True)
    ad = (gdf.groupby('날짜_date').size().reset_index(name='수')
          .rename(columns={'날짜_date':'날짜'}).sort_values('날짜'))
    ad['날짜']  = pd.to_datetime(ad['날짜'])
    ad['누적']  = ad['수'].cumsum()
    line = alt.Chart(ad).mark_line(color='#3b82f6',strokeWidth=2.5).encode(
        x=alt.X('날짜:T',title=''),
        y=alt.Y('누적:Q',title='',axis=alt.Axis(format=',d')),
        tooltip=[alt.Tooltip('날짜:T',format='%Y-%m-%d'),alt.Tooltip('누적:Q',title='누적',format=',')])
    area = alt.Chart(ad).mark_area(color='#3b82f6',opacity=0.08).encode(
        x='날짜:T', y='누적:Q')
    st.altair_chart(
        (line + area).properties(height=180)
        .configure_view(strokeWidth=0).configure_axis(grid=True,gridColor='#f5f5f5'),
        use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 최근 게시글 목록
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tc, bc2 = st.columns([6,2])
    with tc: st.markdown('<p class="card-title">📝 최근 수집 게시글 (최신 50건)</p>', unsafe_allow_html=True)
    with bc2:
        if su.startswith('http'): st.link_button("📊 전체 시트 열기 →", su, use_container_width=True)
    recent = gdf.sort_values('날짜_dt',ascending=False).head(50)
    st.dataframe(
        recent[['글번호','제목','작성자','날짜','댓글수','조회수','추천수']].reset_index(drop=True),
        use_container_width=True, hide_index=True,
        column_config={
            '글번호':  st.column_config.TextColumn('글번호',  width='small'),
            '제목':    st.column_config.TextColumn('제목',    width='large'),
            '작성자':  st.column_config.TextColumn('작성자',  width='small'),
            '날짜':    st.column_config.TextColumn('날짜',    width='medium'),
            '댓글수':  st.column_config.NumberColumn('💬 댓글', width='small'),
            '조회수':  st.column_config.NumberColumn('👁️ 조회', width='small'),
            '추천수':  st.column_config.NumberColumn('👍 추천', width='small'),
        })
    st.markdown('</div>', unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────

def render_sidebar(df, nc, ic, counts):
    with st.sidebar:
        st.markdown("""
        <div style="padding:22px 20px 14px">
          <p style="font-size:17px;font-weight:900;color:#1f2937;margin:0">⛏️ DC-Pickaxe</p>
          <p style="font-size:11px;color:#9ca3af;margin:3px 0 0">갤러리 수집 관제 시스템</p>
        </div>
        <div style="height:1px;background:#f0f0f0;margin:0 16px"></div>
        <div style="padding:14px 20px 4px">
          <p style="font-size:10px;font-weight:700;color:#bbb;letter-spacing:1px;text-transform:uppercase;margin:0">MENU</p>
        </div>""", unsafe_allow_html=True)

        if st.button("🏠  메인 대시보드", use_container_width=True, key="sb_main"):
            st.session_state.page = 'main'; st.rerun()

        if df is not None and not df.empty:
            st.markdown("""<div style="padding:14px 20px 4px">
              <p style="font-size:10px;font-weight:700;color:#bbb;letter-spacing:1px;text-transform:uppercase;margin:0">갤러리</p>
            </div>""", unsafe_allow_html=True)
            for i, (_, row) in enumerate(df.iterrows()):
                gn  = str(row.get(nc,''))
                gid = str(row.get(ic,'')) if ic else str(i)
                cnt = counts.get(gn,-1)
                lbl = f"📊  {gn}" + (f"  ({cnt:,})" if cnt >= 0 else "")
                if st.button(lbl, use_container_width=True, key=f"sb_{gid}"):
                    st.session_state.page = gid; st.rerun()

        st.markdown("""
        <div style="position:fixed;bottom:0;padding:12px 20px;border-top:1px solid #f0f0f0;background:white;width:inherit">
          <p style="font-size:11px;color:#9ca3af;margin:0">DC-Pickaxe v2.1 · PM 김무길</p>
        </div>""", unsafe_allow_html=True)


# ── App Entry ─────────────────────────────────────────────────

if 'page' not in st.session_state:
    st.session_state.page = 'main'

df = load_master()
if df is None or df.empty:
    st.error("❌ GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")
    st.stop()

nc = find_col(df,'명') or df.columns[0]
ic = find_col(df,'ID','id') or (df.columns[1] if len(df.columns)>1 else None)
uc = find_col(df,'URL','url','시트')
rc = find_col(df,'시각','시간') or (df.columns[3] if len(df.columns)>3 else None)
lc = find_col(df,'개수','결과') or (df.columns[4] if len(df.columns)>4 else None)

# 게시글 수 (sidebar 표시용 + 메인 페이지용)
counts: dict[str,int] = {}
if uc:
    for _,row in df.iterrows():
        url = str(row.get(uc,''))
        gn  = str(row.get(nc,''))
        if url.startswith('http'):
            counts[gn] = get_count(url)

render_sidebar(df, nc, ic, counts)

if st.session_state.page == 'main':
    page_main(df, nc, ic, uc, rc, lc, counts)
else:
    match = df[df[ic] == st.session_state.page] if ic and ic in df.columns else pd.DataFrame()
    if not match.empty:
        page_gallery(match.iloc[0], nc, ic, uc, rc, lc)
    else:
        st.session_state.page = 'main'; st.rerun()

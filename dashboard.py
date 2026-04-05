"""DC-Pickaxe 관제탑 — 진입점 및 라우팅"""
import streamlit as st
from dash_data import load_master, load_config, get_count, find_col, KST
from dash_styles import inject_css
from dash_charts import CHART_COLORS
import dash_main
import dash_gallery

st.set_page_config(
    page_title="DC-Pickaxe 관제탑",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="auto",  # 모바일에서 자동 접힘
)
inject_css()

# ── 세션 상태 초기화 ─────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "main"

# ── 데이터 로드 ──────────────────────────────────────────────────
cfg = load_config()
df  = load_master()

if df is None or df.empty:
    st.error("❌ GCP_CREDENTIALS / MASTER_SHEET_URL 환경변수를 확인하세요.")
    st.stop()

nc = find_col(df, "명") or df.columns[0]
ic = find_col(df, "ID", "id") or (df.columns[1] if len(df.columns) > 1 else None)
uc = find_col(df, "URL", "url", "시트")
rc = find_col(df, "시각", "시간") or (df.columns[3] if len(df.columns) > 3 else None)
lc = find_col(df, "개수", "결과") or (df.columns[4] if len(df.columns) > 4 else None)

# 갤러리별 게시글 수 (캐시됨)
counts: dict = {}
if uc:
    for _, row in df.iterrows():
        url = str(row.get(uc, ""))
        gn  = str(row.get(nc, ""))
        if url.startswith("http"):
            counts[gn] = get_count(url)


# ── 사이드바 ─────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='padding:24px 20px 14px'>"
            f"<p style='font-size:17px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ {cfg['app_title']}</p>"
            f"<p class='sub' style='margin:3px 0 0'>{cfg['app_subtitle']}</p>"
            "</div>"
            "<div style='height:1.5px;background:#1E1E1E;margin:0 16px'></div>"
            "<div style='padding:14px 20px 4px'>"
            f"<p style='font-size:10px;font-weight:700;color:#757575;"
            f"letter-spacing:1px;text-transform:uppercase;margin:0'>"
            f"{cfg.get('sidebar_sec_menu', 'MENU')}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button(cfg.get("sidebar_menu_home", "🏠 메인 대시보드"), use_container_width=True, key="sb_main"):
            st.session_state.page = "main"
            st.rerun()
        if st.button(cfg.get("sidebar_refresh", "🔄 새로고침"), use_container_width=True, key="sb_refresh"):
            st.cache_data.clear()
            st.rerun()
        if not df.empty:
            st.markdown(
                "<div style='padding:14px 20px 4px'>"
                f"<p style='font-size:10px;font-weight:700;color:#757575;"
                f"letter-spacing:1px;text-transform:uppercase;margin:0'>"
                f"{cfg.get('sidebar_sec_gall', '갤러리')}</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            for i, (_, row) in enumerate(df.iterrows()):
                gn  = str(row.get(nc, ""))
                gid = str(row.get(ic, "")) if ic else str(i)
                cnt = counts.get(gn, -1)
                lbl = f"📊  {gn}" + (f"  ({cnt:,})" if cnt >= 0 else "")
                if st.button(lbl, use_container_width=True, key=f"sb_{gid}"):
                    st.session_state.page = gid
                    st.rerun()
        st.markdown(
            "<div style='padding:16px 20px;border-top:1px solid #E5E5E5;margin-top:20px'>"
            f"<p class='sub' style='margin:0'>DC-Pickaxe {cfg['app_version']}</p>"
            f"<p class='sub' style='margin:2px 0 0'>PM : {cfg['pm_name']}</p>"
            "<p class='sub' style='margin:6px 0 0;font-size:10px;color:#AAAAAA'>"
            "📱 모바일에서는 좌상단 ≡ 버튼으로 메뉴 열기</p>"
            "</div>",
            unsafe_allow_html=True,
        )


render_sidebar()

# ── 페이지 라우팅 ─────────────────────────────────────────────────
if st.session_state.page == "main":
    dash_main.render(df, nc, ic, uc, rc, lc, counts, cfg)
else:
    if ic and ic in df.columns:
        match = df[df[ic] == st.session_state.page]
    else:
        match = df.iloc[[0]] if not df.empty else df.iloc[0:0]

    if not match.empty:
        dash_gallery.render(match.iloc[0], nc, ic, uc, rc, lc, cfg)
    else:
        st.session_state.page = "main"
        st.rerun()

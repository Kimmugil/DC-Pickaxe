"""DC-Pickaxe CSS — Clean Line Bento Design System"""
import streamlit as st

_CSS = (
    # ── Base ──────────────────────────────────────────────────────
    ".stApp,[data-testid='stAppViewContainer']>.main{"
    "background:#F4F5F7!important;color:#1E1E1E!important}"
    "[data-testid='stHeader']{background:transparent!important;box-shadow:none!important}"
    "[data-testid='stToolbar']{display:none!important}"
    ".block-container{padding:1rem 1.4rem!important;max-width:1340px!important}"

    # ── 모바일 ≡ 버튼 강제 표시 ───────────────────────────────────
    "[data-testid='stSidebarCollapsedControl']{"
    "display:flex!important;visibility:visible!important;opacity:1!important;"
    "pointer-events:auto!important}"

    # ── Sidebar ────────────────────────────────────────────────────
    "section[data-testid='stSidebar']{"
    "background:#FFFFFF!important;"
    "border-right:1.5px solid #1E1E1E!important}"
    "section[data-testid='stSidebar'] .block-container{"
    "padding:0 0 80px 0!important;max-width:none!important}"

    # ── 버튼: 메인 영역 ───────────────────────────────────────────
    "[data-testid='stMain'] [data-testid='baseButton-secondary']{"
    "background:#FFFFFF!important;border:1.5px solid #1E1E1E!important;"
    "border-radius:10px!important;color:#1E1E1E!important;font-weight:600!important;"
    "box-shadow:none!important;font-size:13px!important}"
    "[data-testid='stMain'] [data-testid='baseButton-secondary']:hover{"
    "background:#F4F5F7!important}"

    # ── 버튼: 사이드바 ────────────────────────────────────────────
    "section[data-testid='stSidebar'] [data-testid='baseButton-secondary']{"
    "background:transparent!important;border:1.5px solid #1E1E1E!important;"
    "box-shadow:none!important;color:#1E1E1E!important;font-weight:500!important;"
    "padding:8px 14px!important;border-radius:8px!important;font-size:13px!important;"
    "width:calc(100% - 16px)!important;margin:2px 8px!important;"
    "transition:background .12s!important;"
    "display:flex!important;align-items:center!important;"
    "justify-content:flex-start!important;text-align:left!important}"
    "section[data-testid='stSidebar'] [data-testid='baseButton-secondary'] p,"
    "section[data-testid='stSidebar'] [data-testid='baseButton-secondary'] div{"
    "text-align:left!important;width:100%!important;margin:0!important;"
    "justify-content:flex-start!important}"
    "section[data-testid='stSidebar'] [data-testid='baseButton-secondary']:hover{"
    "background:#F4F5F7!important}"

    # ── st.container(border=True) 오버라이드 → .lc 스타일 적용 ──
    "[data-testid='stVerticalBlockBorderWrapper']{"
    "background:#FFFFFF!important;border:1.5px solid #1E1E1E!important;"
    "border-radius:20px!important}"

    # ── Cards ──────────────────────────────────────────────────────
    ".lc{background:#FFFFFF;border:1.5px solid #1E1E1E;border-radius:20px;"
    "padding:22px 24px;margin-bottom:12px;word-break:keep-all}"
    ".mc{background:#FFFFFF;border:1.5px solid #1E1E1E;border-radius:20px;"
    "padding:20px 14px;text-align:center;margin-bottom:12px;word-break:keep-all}"
    ".mval{font-size:24px;font-weight:800;color:#1E1E1E;line-height:1.2}"
    ".mlbl{font-size:10px;color:#757575;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.7px;margin-top:4px}"
    ".msub{font-size:11px;color:#757575;margin-top:2px}"

    # ── Typography ────────────────────────────────────────────────
    ".ctitle{font-size:14px;font-weight:700;color:#1E1E1E;margin:0 0 14px;word-break:keep-all}"
    ".sec{font-size:14px;font-weight:700;color:#1E1E1E;"
    "border-left:3px solid #1E1E1E;padding-left:10px;margin:20px 0 10px}"
    ".sub{font-size:11px;color:#757575}"

    # ── 배지 ──────────────────────────────────────────────────────
    ".bdg{display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;"
    "font-weight:700;border:1.5px solid;white-space:nowrap}"
    ".bok{border-color:#82C29A;color:#1a6b3a;background:#f0faf3}"
    ".bnfo{border-color:#6DC2FF;color:#0e5c8f;background:#eff8ff}"
    ".berr{border-color:#FF9F9F;color:#9b1c1c;background:#fff0f0}"
    ".bnone{border-color:#CCCCCC;color:#757575;background:#F9F9F9}"

    # ── 인기글 카드 ────────────────────────────────────────────────
    ".hc{background:#FFFCF0;border:1.5px solid #1E1E1E;border-radius:14px;"
    "padding:14px 16px;margin-bottom:0;word-break:keep-all;height:100%}"
    ".hc-gal{font-size:10px;font-weight:700;color:#757575;"
    "text-transform:uppercase;letter-spacing:.6px;margin:0 0 6px}"
    ".hc-title{font-size:13px;font-weight:700;color:#1E1E1E;"
    "margin:0 0 6px;display:-webkit-box;-webkit-line-clamp:2;"
    "-webkit-box-orient:vertical;overflow:hidden}"
    ".hc-meta{font-size:11px;color:#757575;margin-top:4px}"
    ".hc-score{display:inline-block;background:#FFD166;border:1.5px solid #1E1E1E;"
    "border-radius:6px;font-size:11px;font-weight:700;padding:1px 7px;margin-bottom:6px}"

    # ── 테이블 행 카드 ─────────────────────────────────────────────
    ".rc{background:#FFFFFF;border:1.5px solid #E5E5E5;border-radius:10px;"
    "padding:10px 13px;font-size:13px;color:#1E1E1E;margin-bottom:4px;"
    "word-break:keep-all}"
    ".th{font-size:10px;color:#757575;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.6px;padding:0 4px;margin-bottom:2px}"

    # ── 링크 버튼 ─────────────────────────────────────────────────
    ".stLinkButton>a{background:#FFFFFF!important;color:#1E1E1E!important;"
    "border:1.5px solid #1E1E1E!important;border-radius:8px!important;"
    "font-size:12px!important;font-weight:600!important}"
    ".stLinkButton>a:hover{background:#F4F5F7!important}"

    # ── Expander / dataframe ──────────────────────────────────────
    "[data-testid='stExpander']{"
    "background:#FFFFFF!important;border-radius:14px!important;"
    "border:1.5px solid #1E1E1E!important}"
    "[data-testid='stDataFrame']{border-radius:12px;overflow:hidden}"

    # ── 모바일 반응형 ─────────────────────────────────────────────
    "@media(max-width:640px){"
    ".block-container{padding:.5rem .5rem!important}"
    ".lc{padding:14px 12px!important;border-radius:14px!important}"
    ".mc{padding:12px 8px!important;border-radius:14px!important}"
    ".mval{font-size:18px!important}"
    ".mlbl{font-size:9px!important}"
    ".sec{font-size:13px!important}"
    ".ctitle{font-size:13px!important}}"
)


def inject_css():
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

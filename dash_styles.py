"""DC-Pickaxe CSS — Clean Line Bento Design System"""
import streamlit as st

_CSS = (
    # ── Base ──────────────────────────────────────────────────────
    ".stApp,[data-testid='stAppViewContainer']>.main{"
    "background:#F4F5F7!important;color:#1E1E1E!important}"
    "[data-testid='stHeader']{background:transparent!important;box-shadow:none!important}"
    "[data-testid='stToolbar']{display:none!important}"
    ".block-container{padding:1rem 1.4rem!important;max-width:1340px!important}"

    # ── Sidebar ────────────────────────────────────────────────────
    "section[data-testid='stSidebar']{"
    "background:#FFFFFF!important;"
    "border-right:1.5px solid #1E1E1E!important}"
    "section[data-testid='stSidebar'] .block-container{"
    "padding:0!important;max-width:none!important}"
    "section[data-testid='stSidebar'] .stButton>button{"
    "background:transparent!important;border:none!important;box-shadow:none!important;"
    "text-align:left!important;color:#1E1E1E!important;font-weight:500!important;"
    "padding:9px 20px!important;border-radius:0!important;font-size:13.5px!important;"
    "width:100%!important;transition:background .12s!important;"
    "border-left:3px solid transparent!important}"
    "section[data-testid='stSidebar'] .stButton>button:hover{"
    "background:#F4F5F7!important;border-left-color:#1E1E1E!important}"

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
    ".sec{font-size:15px;font-weight:700;color:#1E1E1E;"
    "border-left:3px solid #1E1E1E;padding-left:10px;margin:20px 0 10px}"
    ".sub{font-size:11px;color:#757575}"

    # ── Badges ────────────────────────────────────────────────────
    ".bdg{display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;"
    "font-weight:700;border:1.5px solid;white-space:nowrap}"
    ".bok{border-color:#82C29A;color:#1a6b3a;background:#f0faf3}"
    ".bnfo{border-color:#6DC2FF;color:#0e5c8f;background:#eff8ff}"
    ".berr{border-color:#FF9F9F;color:#9b1c1c;background:#fff0f0}"
    ".bnone{border-color:#CCCCCC;color:#757575;background:#F9F9F9}"

    # ── Hot post card ─────────────────────────────────────────────
    ".hc{background:#FFFCF0;border:1.5px solid #FFD166;border-radius:12px;"
    "padding:12px 14px;margin-bottom:8px;word-break:keep-all}"
    ".hc-title{font-size:13px;font-weight:700;color:#1E1E1E;"
    "margin:0 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
    ".hc-meta{font-size:11px;color:#757575}"

    # ── Table row card ────────────────────────────────────────────
    ".rc{background:#FFFFFF;border:1.5px solid #E5E5E5;border-radius:10px;"
    "padding:10px 13px;font-size:13px;color:#1E1E1E;margin-bottom:4px;"
    "word-break:keep-all}"
    ".th{font-size:10px;color:#757575;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.6px;padding:0 4px;margin-bottom:2px}"

    # ── Link button ───────────────────────────────────────────────
    ".stLinkButton>a{background:#FFFFFF!important;color:#1E1E1E!important;"
    "border:1.5px solid #1E1E1E!important;border-radius:8px!important;"
    "font-size:12px!important;font-weight:600!important}"
    ".stLinkButton>a:hover{background:#F4F5F7!important}"

    # ── Expander / dataframe ──────────────────────────────────────
    "[data-testid='stExpander']{"
    "background:#FFFFFF!important;border-radius:14px!important;"
    "border:1.5px solid #1E1E1E!important}"
    "[data-testid='stDataFrame']{border-radius:12px;overflow:hidden}"

    # ── Mobile responsive ─────────────────────────────────────────
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

"""DC-Pickaxe 메인 대시보드 페이지"""
import re
import streamlit as st
from datetime import datetime
from dash_data import KST, time_ago, bdg, load_gallery, get_hot_posts
from dash_charts import CHART_COLORS


def render(df, nc, ic, uc, rc, lc, counts, cfg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # ── 통계 계산 ──────────────────────────────────────────────────
    tp = sum(v for v in counts.values() if v >= 0)
    this_run = 0
    if lc:
        for v in df[lc]:
            m = re.search(r"(\d+)개", str(v))
            if m:
                this_run += int(m.group(1))
    lr = str(df[rc].iloc[0]) if rc and not df.empty else ""

    # ── 히어로 카드: 헤더 + KPI 통합 (순수 HTML) ───────────────────
    ann = cfg.get("announcement", "").strip()
    ann_html = (
        f"<div style='margin:10px 0 0;padding:7px 12px;background:#FFFCF0;"
        f"border:1px solid #FFD166;border-radius:8px;font-size:12px;font-weight:600'>"
        f"📢 {ann}</div>"
    ) if ann else ""

    kpi_data = [
        (f"{tp:,}건",        cfg.get("kpi_total_posts", "총 수집 게시글"), "#F0FAF3", True),
        (f"{this_run:,}건",  cfg.get("kpi_this_run",   "이번 수집량"),     "#FFFCF0", True),
        (time_ago(lr),       cfg.get("kpi_last_run",   "마지막 실행"),     "#EFF8FF", False),
    ]
    kpi_html = ""
    for val, lbl, bg, has_border in kpi_data:
        br = "border-right:1.5px solid #1E1E1E;" if has_border else ""
        kpi_html += (
            f"<div style='flex:1;padding:14px 20px;background:{bg};{br}min-width:0'>"
            f"<div style='font-size:22px;font-weight:900;color:#1E1E1E;"
            f"line-height:1.1;word-break:keep-all'>{val}</div>"
            f"<div style='font-size:10px;color:#757575;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-top:5px'>{lbl}</div>"
            f"</div>"
        )

    st.markdown(
        "<div class='lc' style='margin-bottom:14px;padding:0;overflow:hidden'>"
        "<div style='padding:20px 24px'>"
        f"<p style='font-size:19px;font-weight:900;color:#1E1E1E;margin:0'>"
        f"⛏️ {cfg['app_title']}</p>"
        f"<p class='sub' style='margin:4px 0 0'>{cfg['app_subtitle']}</p>"
        f"<p class='sub' style='margin:4px 0 0'>🕐 {now} (KST)</p>"
        f"{ann_html}"
        "</div>"
        f"<div style='display:flex;border-top:1.5px solid #1E1E1E'>{kpi_html}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 갤러리별 수집 현황 (카드 없이 깔끔하게) ──────────────────────
    st.markdown(
        f"<p class='sec'>{cfg.get('title_table', '📋 갤러리별 수집 현황')}</p>",
        unsafe_allow_html=True,
    )

    # 컬럼 헤더
    hcols = st.columns([2.6, 2, 1.6, 1.8, 3.4])
    for hc, ht in zip(hcols, [
        cfg.get("col_gallery",  "갤러리"),
        cfg.get("col_status",   "수집 상태"),
        cfg.get("col_posts",    "게시글"),
        cfg.get("col_last_run", "마지막 실행"),
        cfg.get("col_hot",      "인기글"),
    ]):
        hc.markdown(f"<p class='th'>{ht}</p>", unsafe_allow_html=True)

    st.markdown(
        "<div style='height:1px;background:#1E1E1E;margin:2px 0 6px'></div>",
        unsafe_allow_html=True,
    )

    # 데이터 행
    for i, (_, row) in enumerate(df.iterrows()):
        gn  = str(row.get(nc, ""))
        gi  = str(row.get(ic, "")) if ic else str(i)
        rm  = str(row.get(lc, "")) if lc else ""
        lr2 = str(row.get(rc, "")) if rc else ""
        su  = str(row.get(uc, "")) if uc else ""
        cnt = counts.get(gn, -1)
        cnt_txt = f"{cnt:,}건" if cnt >= 0 else "—"

        c1, c2, c3, c4, c5 = st.columns([2.6, 2, 1.6, 1.8, 3.4])

        with c1:
            if st.button(gn, key=f"tbl_{gi}", use_container_width=True):
                st.session_state.page = gi
                st.rerun()
            st.markdown(
                f"<p class='sub' style='margin:-2px 0 4px;padding-left:2px'>{gi}</p>",
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                f"<div style='padding-top:6px'>{bdg(rm)}</div>",
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown(
                f"<p class='rc' style='font-weight:700'>{cnt_txt}</p>",
                unsafe_allow_html=True,
            )

        with c4:
            st.markdown(
                f"<p class='rc sub'>🕐 {time_ago(lr2)}</p>",
                unsafe_allow_html=True,
            )

        with c5:
            hot_html = "<div style='padding-top:4px'>"
            if su.startswith("http"):
                gdf = load_gallery(su)
                hot, _ = get_hot_posts(gdf, n=1)
                if not hot.empty:
                    hr    = hot.iloc[0]
                    link  = str(hr.get("링크", ""))
                    title = str(hr.get("제목", ""))
                    rec   = int(hr.get("추천수", 0))
                    cmt   = int(hr.get("댓글수", 0))
                    t_short = title[:20] + "…" if len(title) > 20 else title
                    t_html = (
                        f"<a href='{link}' target='_blank'"
                        f" style='color:#1E1E1E;text-decoration:none'>{t_short}</a>"
                        if link.startswith("http") else t_short
                    )
                    hot_html += (
                        f"<div style='font-size:12px;font-weight:600;"
                        f"line-height:1.4;margin-bottom:2px'>🔥 {t_html}</div>"
                        f"<div class='sub'>👍 {rec} &nbsp; 💬 {cmt}</div>"
                    )
                else:
                    hot_html += "<span class='sub'>—</span>"
            else:
                hot_html += "<span class='sub'>—</span>"
            hot_html += "</div>"
            st.markdown(hot_html, unsafe_allow_html=True)

        if i < len(df) - 1:
            st.markdown(
                "<div style='height:1px;background:#E5E5E5;margin:4px 0'></div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"<p class='sub' style='text-align:right;margin-top:6px'>"
        f"💡 {cfg.get('collection_note', '봇 실행 시 갱신 (1시간 주기)')}</p>",
        unsafe_allow_html=True,
    )

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:24px;padding-top:12px;"
        f"border-top:1px solid #E5E5E5'>"
        f"<span class='sub'>PM : {cfg['pm_name']} &nbsp;|&nbsp; "
        f"DC-Pickaxe {cfg['app_version']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

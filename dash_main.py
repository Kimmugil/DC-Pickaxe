"""DC-Pickaxe 메인 대시보드 페이지"""
import re
import streamlit as st
from datetime import datetime
from dash_data import KST, time_ago, bdg, load_gallery, get_hot_posts
from dash_charts import CHART_COLORS, svg_bar_h


def render(df, nc, ic, uc, rc, lc, counts, cfg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # ── 헤더 ──────────────────────────────────────────────────────
    ann = cfg.get("announcement", "").strip()
    ann_html = (
        f"<div style='margin-top:8px;padding:6px 10px;background:#FFFCF0;"
        f"border:1px solid #FFD166;border-radius:8px;font-size:12px;font-weight:600'>"
        f"📢 {ann}</div>"
    ) if ann else ""
    st.markdown(
        "<div class='lc' style='margin-bottom:14px;padding:18px 22px'>"
        "<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        "<div>"
        f"<p style='font-size:19px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ {cfg['app_title']}</p>"
        f"<p class='sub' style='margin:3px 0 0'>{cfg['app_subtitle']}</p>"
        f"<p class='sub' style='margin:5px 0 0'>🕐 {now} (KST)</p>"
        "</div>"
        "</div>"
        f"{ann_html}"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── KPI 카드 3개 ───────────────────────────────────────────────
    tp = sum(v for v in counts.values() if v >= 0)
    this_run = 0
    if lc:
        for v in df[lc]:
            m = re.search(r"(\d+)개", str(v))
            if m:
                this_run += int(m.group(1))
    lr = str(df[rc].iloc[0]) if rc and not df.empty else ""

    m1, m2, m3 = st.columns(3)
    for col, icon, val, lbl, sub in [
        (m1, "📄", f"{tp:,}건",       cfg.get("kpi_total_posts", "총 수집 게시글"), cfg.get("kpi_total_sub", "전체 갤러리 합산")),
        (m2, "🔄", f"{this_run:,}건", cfg.get("kpi_this_run",   "이번 수집량"),     cfg.get("kpi_this_run_sub", "최근 1회 실행 합계")),
        (m3, "🕐", time_ago(lr),      cfg.get("kpi_last_run",   "마지막 실행"),     cfg.get("kpi_last_run_sub", "봇 최근 실행")),
    ]:
        with col:
            st.markdown(
                f"<div class='mc'>"
                f"<div style='font-size:20px;margin-bottom:6px'>{icon}</div>"
                f"<div class='mval'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div>"
                f"<div class='msub'>{sub}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 갤러리 현황 테이블 + 바 차트 (2분할) ──────────────────────
    tbl_col, chart_col = st.columns([6, 4])

    with tbl_col:
        with st.container(border=True):
            st.markdown(
                f"<p class='ctitle' style='padding:4px 4px 0'>"
                f"{cfg.get('title_table', '📋 갤러리별 수집 현황')}</p>",
                unsafe_allow_html=True,
            )
            # 헤더 행
            hcols = st.columns([2.8, 2, 1.6, 1.8, 3.2])
            for hc, ht in zip(hcols, [
                cfg.get("col_gallery",  "갤러리"),
                cfg.get("col_status",   "수집 상태"),
                cfg.get("col_posts",    "게시글"),
                cfg.get("col_last_run", "마지막 실행"),
                cfg.get("col_hot",      "인기글"),
            ]):
                hc.markdown(f"<p class='th'>{ht}</p>", unsafe_allow_html=True)

            # 데이터 행
            st.markdown("<hr style='border:none;border-top:1px solid #E5E5E5;margin:4px 0'>", unsafe_allow_html=True)
            for i, (_, row) in enumerate(df.iterrows()):
                color = CHART_COLORS[i % len(CHART_COLORS)]
                gn  = str(row.get(nc, ""))
                gi  = str(row.get(ic, "")) if ic else str(i)
                rm  = str(row.get(lc, "")) if lc else ""
                lr2 = str(row.get(rc, "")) if rc else ""
                su  = str(row.get(uc, "")) if uc else ""
                cnt = counts.get(gn, -1)
                cnt_txt = f"{cnt:,}건" if cnt >= 0 else "—"

                c1, c2, c3, c4, c5 = st.columns([2.8, 2, 1.6, 1.8, 3.2])

                with c1:
                    if st.button(gn, key=f"tbl_{gi}", use_container_width=True):
                        st.session_state.page = gi
                        st.rerun()
                    st.markdown(
                        f"<p class='sub' style='margin:-2px 0 6px;padding-left:2px'>{gi}</p>",
                        unsafe_allow_html=True,
                    )

                with c2:
                    st.markdown(
                        f"<div style='padding-top:6px'>{bdg(rm)}</div>",
                        unsafe_allow_html=True,
                    )

                with c3:
                    st.markdown(
                        f"<div class='rc' style='margin-top:6px;font-weight:700'>"
                        f"{cnt_txt}</div>",
                        unsafe_allow_html=True,
                    )

                with c4:
                    st.markdown(
                        f"<div class='rc sub' style='margin-top:6px'>"
                        f"🕐 {time_ago(lr2)}</div>",
                        unsafe_allow_html=True,
                    )

                with c5:
                    # 인기글 TOP 1 인라인
                    hot_html = "<div style='padding-top:6px'>"
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
                                f"line-height:1.4;margin-bottom:3px'>🔥 {t_html}</div>"
                                f"<div class='sub'>👍 {rec} &nbsp; 💬 {cmt}</div>"
                            )
                        else:
                            hot_html += "<span class='sub'>—</span>"
                    else:
                        hot_html += "<span class='sub'>—</span>"
                    hot_html += "</div>"
                    st.markdown(hot_html, unsafe_allow_html=True)

                # 행 구분선
                if i < len(df) - 1:
                    st.markdown(
                        "<hr style='border:none;border-top:1px solid #E5E5E5;margin:2px 0'>",
                        unsafe_allow_html=True,
                    )

            st.markdown(
                f"<p class='sub' style='text-align:right;margin-top:4px'>"
                f"💡 {cfg.get('collection_note', '봇 실행 시 갱신 (1시간 주기)')}</p>",
                unsafe_allow_html=True,
            )

    with chart_col:
        bar_svg = svg_bar_h({k: max(v, 0) for k, v in counts.items()}) if counts else ""
        if bar_svg:
            st.markdown(
                "<div class='lc'>"
                f"<p class='ctitle'>{cfg.get('title_chart', '📊 갤러리별 수집 게시글')}</p>"
                f"{bar_svg}"
                "</div>",
                unsafe_allow_html=True,
            )

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:20px;padding-top:12px;"
        f"border-top:1px solid #E5E5E5'>"
        f"<span class='sub'>PM : {cfg['pm_name']} &nbsp;|&nbsp; DC-Pickaxe {cfg['app_version']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

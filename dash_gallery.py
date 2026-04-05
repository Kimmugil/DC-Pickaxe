"""DC-Pickaxe 갤러리 상세 페이지"""
import streamlit as st
from dash_data import KST, time_ago, bdg, load_gallery, get_hot_posts
from dash_charts import svg_line_area, svg_bar_daily


def render(row, nc, ic, uc, rc, lc, cfg):
    gn = str(row.get(nc, ""))
    gi = str(row.get(ic, "")) if ic else ""
    su = str(row.get(uc, "")) if uc else ""
    lr = str(row.get(rc, "")) if rc else ""
    rm = str(row.get(lc, "")) if lc else ""

    with st.spinner("갤러리 데이터 로딩 중..."):
        gdf = load_gallery(su)

    if gdf.empty:
        st.info(cfg.get("msg_gall_no_data", "수집된 게시글이 없습니다. 온보딩 스크래퍼를 실행해주세요."))
        return

    total = len(gdf)
    vd    = gdf["날짜_date"].dropna()
    dmin  = vd.min() if len(vd) else None
    dmax  = vd.max() if len(vd) else None
    days  = max((dmax - dmin).days + 1, 1) if dmin and dmax else 1
    avg   = round(total / days, 1)

    # ── 히어로 카드: 헤더 + KPI 통합 (순수 HTML) ───────────────────
    kpi_data = [
        (f"{total:,}건",               cfg.get("kpi_gall_total",  "총 수집 게시글"), "#F0FAF3", True),
        (str(dmin) if dmin else "—",   cfg.get("kpi_gall_first",  "최초 수집"),      "#FFFCF0", True),
        (str(dmax) if dmax else "—",   cfg.get("kpi_gall_recent", "최근 수집"),      "#EFF8FF", True),
        (f"{avg}건/일",                 cfg.get("kpi_gall_avg",    "일평균"),         "#FFFFFF", False),
    ]
    kpi_html = ""
    for val, lbl, bg, has_border in kpi_data:
        br = "border-right:1.5px solid #1E1E1E;" if has_border else ""
        kpi_html += (
            f"<div style='flex:1;padding:12px 18px;background:{bg};{br}min-width:0'>"
            f"<div style='font-size:18px;font-weight:900;color:#1E1E1E;"
            f"line-height:1.1;word-break:break-all'>{val}</div>"
            f"<div style='font-size:10px;color:#757575;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-top:4px'>{lbl}</div>"
            f"</div>"
        )

    st.markdown(
        "<div class='lc' style='margin-bottom:14px;padding:0;overflow:hidden'>"
        "<div style='padding:18px 24px'>"
        f"<p style='font-size:18px;font-weight:900;color:#1E1E1E;margin:0'>📊 {gn}</p>"
        f"<p class='sub' style='margin:4px 0 0'>"
        f"ID: {gi} &nbsp;|&nbsp; 최근 수집: {time_ago(lr)} &nbsp;|&nbsp; {bdg(rm)}"
        f"</p>"
        "</div>"
        f"<div style='display:flex;border-top:1.5px solid #1E1E1E'>{kpi_html}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 2분할: 인기글 카드 | 차트 2개 ────────────────────────────
    hot_col, chart_col = st.columns([42, 58])

    # ── 왼쪽: 인기글 TOP 3 — 하나의 카드 안에 ─────────────────────
    with hot_col:
        hot, period = get_hot_posts(gdf, n=3)

        items_html = ""
        if hot.empty:
            items_html = "<p class='sub' style='margin:0'>데이터 없음</p>"
        else:
            for rank, (_, hr) in enumerate(hot.iterrows(), 1):
                link  = str(hr.get("링크", ""))
                title = str(hr.get("제목", ""))
                date  = str(hr.get("날짜", ""))[:10]
                rec   = int(hr.get("추천수", 0))
                cmt   = int(hr.get("댓글수", 0))
                score = int(hr.get("점수", 0))
                title_html = (
                    f"<a href='{link}' target='_blank'"
                    f" style='color:#1E1E1E;text-decoration:none;font-weight:700'>{title}</a>"
                    if link.startswith("http") else
                    f"<span style='font-weight:700'>{title}</span>"
                )
                border_top = "border-top:1px solid #E5E5E5;" if rank > 1 else ""
                items_html += (
                    f"<div style='{border_top}padding:{'14px 0 0' if rank > 1 else '0 0 0'}'>"
                    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
                    f"<span style='display:inline-flex;align-items:center;justify-content:center;"
                    f"width:22px;height:22px;border-radius:50%;background:#FFD166;"
                    f"border:1.5px solid #1E1E1E;font-size:11px;font-weight:900;"
                    f"flex-shrink:0'>{rank}</span>"
                    f"<div style='font-size:13px;line-height:1.4;min-width:0'>{title_html}</div>"
                    f"</div>"
                    f"<div class='sub' style='padding-left:30px'>"
                    f"📅 {date} &nbsp; 👍 {rec} &nbsp; 💬 {cmt}"
                    f"</div>"
                    f"</div>"
                )

        st.markdown(
            "<div class='lc' style='padding:18px 20px'>"
            f"<p class='ctitle' style='margin-bottom:4px'>"
            f"{cfg.get('title_hot_detail', '🔥 인기글 TOP 3')}</p>"
            f"<p class='sub' style='margin:0 0 14px'>{period} 기준</p>"
            f"{items_html}"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── 오른쪽: 차트 2개 (세로 배치) ──────────────────────────────
    with chart_col:
        # 일별 게시글 (최근 30일)
        daily = (
            gdf.groupby("날짜_date")
            .size()
            .reset_index(name="수")
            .sort_values("날짜_date")
            .tail(30)
        )
        dates_list = [str(d) for d in daily["날짜_date"].tolist()]
        vals_list  = daily["수"].tolist()
        bar_svg    = svg_bar_daily(dates_list, vals_list, width=560, height=130)
        st.markdown(
            "<div class='lc' style='padding:16px 20px;margin-bottom:10px'>"
            f"<p class='ctitle' style='margin-bottom:8px'>"
            f"{cfg.get('title_daily', '📅 일별 게시글 (30일)')}</p>"
            f"{bar_svg}"
            "</div>",
            unsafe_allow_html=True,
        )

        # 누적 추이
        all_daily = (
            gdf.groupby("날짜_date")
            .size()
            .reset_index(name="수")
            .sort_values("날짜_date")
        )
        all_daily["누적"] = all_daily["수"].cumsum()
        cumul_vals = all_daily["누적"].tolist()
        line_svg   = svg_line_area(
            cumul_vals, width=560, height=120,
            line_color="#1E1E1E", fill_color="#82C29A", svg_id="cumul"
        )
        dl = all_daily["날짜_date"].tolist()
        dlabels = ""
        if dl:
            for idx in [0, len(dl) - 1]:
                pct = (idx / max(len(dl) - 1, 1)) * 100
                dlabels += (
                    f"<span style='position:absolute;left:{pct:.0f}%;"
                    f"transform:translateX(-50%);font-size:9px;color:#757575'>"
                    f"{str(dl[idx])[5:]}</span>"
                )
        st.markdown(
            "<div class='lc' style='padding:16px 20px'>"
            "<div style='display:flex;justify-content:space-between;"
            "align-items:center;margin-bottom:8px'>"
            f"<p class='ctitle' style='margin:0'>"
            f"{cfg.get('title_cumul', '📈 누적 추이')}</p>"
            f"<span style='font-size:16px;font-weight:800'>{total:,}건</span>"
            "</div>"
            f"{line_svg}"
            f"<div style='position:relative;height:14px;margin-top:2px'>{dlabels}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 최근 게시글 테이블 ────────────────────────────────────────
    tbl_hdr, tbl_btn = st.columns([7, 2])
    with tbl_hdr:
        st.markdown(
            f"<p class='sec'>"
            f"{cfg.get('title_recent_list', '📝 최근 수집 게시글')} (최신 50건)</p>",
            unsafe_allow_html=True,
        )
    with tbl_btn:
        st.markdown("<div style='padding-top:18px'></div>", unsafe_allow_html=True)
        if su.startswith("http"):
            st.link_button(cfg.get("btn_sheet", "📊 전체 시트 →"), su, use_container_width=True)

    recent = gdf.sort_values("날짜_dt", ascending=False).head(50)
    st.dataframe(
        recent[["글번호", "제목", "작성자", "날짜", "댓글수", "조회수", "추천수"]].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=320,
        column_config={
            "글번호":  st.column_config.TextColumn("글번호",  width="small"),
            "제목":    st.column_config.TextColumn("제목",    width="large"),
            "작성자":  st.column_config.TextColumn("작성자",  width="small"),
            "날짜":    st.column_config.TextColumn("날짜",    width="medium"),
            "댓글수":  st.column_config.NumberColumn("💬 댓글", width="small"),
            "조회수":  st.column_config.NumberColumn("👁 조회",  width="small"),
            "추천수":  st.column_config.NumberColumn("👍 추천", width="small"),
        },
    )

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:12px'>"
        f"<span class='sub'>DC-Pickaxe {cfg['app_version']} "
        f"&nbsp;|&nbsp; PM : {cfg['pm_name']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

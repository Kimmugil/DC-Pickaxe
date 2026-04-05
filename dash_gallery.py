"""DC-Pickaxe 갤러리 상세 페이지 — 한 화면 최적화 레이아웃"""
import streamlit as st
from dash_data import KST, time_ago, bdg, load_gallery, get_hot_posts
from dash_charts import svg_line_area, svg_bar_daily


def render(row, nc, ic, uc, rc, lc, cfg):
    gn = str(row.get(nc, ""))
    gi = str(row.get(ic, "")) if ic else ""
    su = str(row.get(uc, "")) if uc else ""
    lr = str(row.get(rc, "")) if rc else ""
    rm = str(row.get(lc, "")) if lc else ""

    # ── 헤더 (새로고침 버튼 통합) ─────────────────────────────────
    st.markdown(
        "<div class='lc' style='margin-bottom:12px;padding:16px 20px'>"
        "<div style='display:flex;justify-content:space-between;align-items:center'>"
        "<div>"
        f"<p style='font-size:18px;font-weight:900;margin:0'>📊 {gn}</p>"
        f"<p class='sub' style='margin:4px 0 0'>"
        f"ID: {gi} &nbsp;|&nbsp; 최근 수집: {time_ago(lr)} &nbsp;|&nbsp; {bdg(rm)}"
        f"</p>"
        "</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, rf_col = st.columns([11, 1])
    with rf_col:
        st.markdown("<div style='margin-top:-60px'></div>", unsafe_allow_html=True)
        if st.button("↺", use_container_width=True, key="rf_gall", help="새로고침"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("갤러리 데이터 로딩 중..."):
        gdf = load_gallery(su)

    if gdf.empty:
        st.info("수집된 게시글이 없습니다. 온보딩 스크래퍼를 실행해주세요.")
        return

    total = len(gdf)
    vd    = gdf["날짜_date"].dropna()
    dmin  = vd.min() if len(vd) else None
    dmax  = vd.max() if len(vd) else None
    days  = max((dmax - dmin).days + 1, 1) if dmin and dmax else 1
    avg   = round(total / days, 1)

    # ── KPI 카드 4개 (컴팩트, 순수 B&W) ──────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    for col, icon, val, lbl in [
        (m1, "📄", f"{total:,}건",             "총 수집 게시글"),
        (m2, "📅", str(dmin) if dmin else "-", "최초 수집"),
        (m3, "🗓️", str(dmax) if dmax else "-", "최근 수집"),
        (m4, "📈", f"{avg}건/일",              "일평균"),
    ]:
        with col:
            st.markdown(
                f"<div class='mc' style='padding:14px 10px'>"
                f"<div style='font-size:18px;margin-bottom:4px'>{icon}</div>"
                f"<div class='mval' style='font-size:18px'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 메인 3분할: 인기글 | 일별 차트 | 누적 차트 ─────────────────
    hot_col, bar_col, line_col = st.columns([38, 32, 30])

    # 왼쪽: 인기글 TOP 3 (컴팩트)
    with hot_col:
        hot, period = get_hot_posts(gdf, n=3)
        period_label = period
        st.markdown(
            f"<div class='lc' style='padding:16px 18px'>"
            f"<p class='ctitle' style='margin-bottom:10px'>🔥 인기글 TOP 3</p>"
            f"<p class='sub' style='margin:-8px 0 10px'>{period_label} 기준</p>",
            unsafe_allow_html=True,
        )
        if hot.empty:
            st.markdown("<p class='sub'>데이터 없음</p>", unsafe_allow_html=True)
        else:
            for rank, (_, hr) in enumerate(hot.iterrows(), 1):
                link  = str(hr.get("링크", ""))
                title = str(hr.get("제목", ""))
                date  = str(hr.get("날짜", ""))[:10]
                rec   = int(hr.get("추천수", 0))
                cmt   = int(hr.get("댓글수", 0))
                title_html = (
                    f"<a href='{link}' target='_blank'"
                    f" style='color:#1E1E1E;text-decoration:none'>{title}</a>"
                    if link.startswith("http") else title
                )
                st.markdown(
                    f"<div style='border:1.5px solid #1E1E1E;border-radius:10px;"
                    f"padding:10px 12px;margin-bottom:8px;background:#FFFCF0'>"
                    f"<div style='font-size:11px;font-weight:900;color:#757575;margin-bottom:3px'>#{rank}</div>"
                    f"<div style='font-size:12px;font-weight:700;color:#1E1E1E;"
                    f"display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden'>"
                    f"{title_html}</div>"
                    f"<div style='font-size:10px;color:#757575;margin-top:4px'>"
                    f"📅 {date} &nbsp; 👍 {rec} &nbsp; 💬 {cmt}"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # 가운데: 일별 게시글 (최근 30일)
    with bar_col:
        daily = (
            gdf.groupby("날짜_date")
            .size()
            .reset_index(name="수")
            .sort_values("날짜_date")
            .tail(30)
        )
        dates_list = [str(d) for d in daily["날짜_date"].tolist()]
        vals_list  = daily["수"].tolist()
        bar_svg    = svg_bar_daily(dates_list, vals_list, width=400, height=120)
        st.markdown(
            "<div class='lc' style='padding:16px 18px'>"
            "<p class='ctitle' style='margin-bottom:8px'>📅 일별 게시글 (30일)</p>"
            f"{bar_svg}"
            "</div>",
            unsafe_allow_html=True,
        )

    # 오른쪽: 누적 추이
    with line_col:
        all_daily = (
            gdf.groupby("날짜_date")
            .size()
            .reset_index(name="수")
            .sort_values("날짜_date")
        )
        all_daily["누적"] = all_daily["수"].cumsum()
        cumul_vals = all_daily["누적"].tolist()
        line_svg   = svg_line_area(
            cumul_vals, width=340, height=120,
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
            "<div class='lc' style='padding:16px 18px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
            "<p class='ctitle' style='margin:0'>📈 누적 추이</p>"
            f"<span style='font-size:16px;font-weight:800'>{total:,}건</span>"
            "</div>"
            f"{line_svg}"
            f"<div style='position:relative;height:14px;margin-top:2px'>{dlabels}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 최근 게시글 테이블 (높이 고정, 화면 내 스크롤) ───────────────
    tbl_hdr, tbl_btn = st.columns([7, 2])
    with tbl_hdr:
        st.markdown("<p class='sec'>📝 최근 수집 게시글 (최신 50건)</p>", unsafe_allow_html=True)
    with tbl_btn:
        st.markdown("<div style='padding-top:18px'></div>", unsafe_allow_html=True)
        if su.startswith("http"):
            st.link_button("📊 전체 시트 →", su, use_container_width=True)
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
        f"<span class='sub'>DC-Pickaxe {cfg['app_version']} &nbsp;|&nbsp; PM : {cfg['pm_name']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

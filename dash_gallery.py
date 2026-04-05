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

    # ── 헤더 ──────────────────────────────────────────────────────
    hcol, rcol = st.columns([9, 1])
    with hcol:
        st.markdown(
            "<div class='lc' style='border-left:5px solid #1E1E1E;border-top-left-radius:6px;"
            "border-bottom-left-radius:6px;margin-bottom:14px'>"
            f"<p style='font-size:19px;font-weight:900;margin:0'>📊 {gn}</p>"
            f"<p class='sub' style='margin:5px 0 0'>"
            f"ID: {gi} &nbsp;|&nbsp; 최근 수집: {time_ago(lr)} &nbsp;|&nbsp; {bdg(rm)}"
            f"</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with rcol:
        st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
        if st.button("🔄", use_container_width=True, key="rf_gall", help="새로고침"):
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

    # ── KPI 카드 (순수 B&W, 색상 악센트 없음) ─────────────────────
    m1, m2, m3, m4 = st.columns(4)
    for col, icon, val, lbl in [
        (m1, "📄", f"{total:,}건",             "총 수집 게시글"),
        (m2, "📅", str(dmin) if dmin else "-", "최초 수집 날짜"),
        (m3, "🗓️", str(dmax) if dmax else "-", "최근 수집 날짜"),
        (m4, "📈", f"{avg}건/일",              "일평균 게시글"),
    ]:
        with col:
            st.markdown(
                f"<div class='mc'>"
                f"<div style='font-size:20px;margin-bottom:6px'>{icon}</div>"
                f"<div class='mval' style='font-size:20px'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── 인기글 TOP 5 (최근 24h 우선, 미달 시 7일) ─────────────────
    hot, period = get_hot_posts(gdf, n=5)
    if not hot.empty:
        st.markdown("<p class='sec'>🔥 인기글 TOP 5</p>", unsafe_allow_html=True)
        st.caption(f"추천수×2 + 댓글수 점수 기준 — {period} 내 게시글")
        for rank, (_, hr) in enumerate(hot.iterrows(), 1):
            link  = str(hr.get("링크", ""))
            title = str(hr.get("제목", ""))
            date  = str(hr.get("날짜", ""))[:10]
            rec   = int(hr.get("추천수", 0))
            cmt   = int(hr.get("댓글수", 0))
            score = int(hr.get("점수", 0))
            href_html = (
                f"<a href='{link}' target='_blank'"
                f" style='color:#1E1E1E;text-decoration:none'>{title}</a>"
                if link.startswith("http") else title
            )
            rank_badge = f"<span style='font-size:15px;font-weight:900;margin-right:8px'>#{rank}</span>"
            st.markdown(
                f"<div class='hc' style='margin-bottom:10px'>"
                f"<div class='hc-title'>{rank_badge}{href_html}</div>"
                f"<div class='hc-meta'>"
                f"📅 {date} &nbsp; 👍 추천 {rec} &nbsp; 💬 댓글 {cmt} &nbsp; 🏆 점수 {score}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── 일별 게시글 수 (최근 60일) ────────────────────────────────
    daily = (
        gdf.groupby("날짜_date")
        .size()
        .reset_index(name="수")
        .sort_values("날짜_date")
        .tail(60)
    )
    dates_list = [str(d) for d in daily["날짜_date"].tolist()]
    vals_list  = daily["수"].tolist()
    bar_svg    = svg_bar_daily(dates_list, vals_list)
    st.markdown(
        "<div class='lc'>"
        "<p class='ctitle'>📅 일별 게시글 수 (최근 60일)</p>"
        f"{bar_svg}"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 누적 추이 ─────────────────────────────────────────────────
    all_daily = (
        gdf.groupby("날짜_date")
        .size()
        .reset_index(name="수")
        .sort_values("날짜_date")
    )
    all_daily["누적"] = all_daily["수"].cumsum()
    cumul_vals = all_daily["누적"].tolist()
    line_svg   = svg_line_area(cumul_vals, line_color="#1E1E1E", fill_color="#82C29A", svg_id="cumul")
    dl = all_daily["날짜_date"].tolist()
    date_label = ""
    if dl:
        for idx in [0, len(dl) // 2, len(dl) - 1]:
            pct = (idx / max(len(dl) - 1, 1)) * 100
            date_label += (
                f"<span style='position:absolute;left:{pct:.0f}%;"
                f"transform:translateX(-50%);font-size:10px;color:#757575'>"
                f"{str(dl[idx])[5:]}</span>"
            )
    st.markdown(
        "<div class='lc'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>"
        "<p class='ctitle' style='margin:0'>📈 누적 게시글 추이</p>"
        f"<span style='font-size:20px;font-weight:800;color:#1E1E1E'>{total:,}건</span>"
        "</div>"
        f"{line_svg}"
        f"<div style='position:relative;height:18px;margin-top:4px'>{date_label}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 최근 게시글 목록 ──────────────────────────────────────────
    tc, bc2 = st.columns([6, 2])
    with tc:
        st.markdown("<p class='sec'>📝 최근 수집 게시글 (최신 50건)</p>", unsafe_allow_html=True)
    with bc2:
        st.markdown("<div style='padding-top:18px'></div>", unsafe_allow_html=True)
        if su.startswith("http"):
            st.link_button("📊 전체 시트 →", su, use_container_width=True)
    recent = gdf.sort_values("날짜_dt", ascending=False).head(50)
    st.dataframe(
        recent[["글번호", "제목", "작성자", "날짜", "댓글수", "조회수", "추천수"]].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
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
        f"<div style='text-align:right;margin-top:16px'>"
        f"<span class='sub'>DC-Pickaxe {cfg['app_version']} &nbsp;|&nbsp; PM : {cfg['pm_name']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

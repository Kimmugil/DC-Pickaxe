"""DC-Pickaxe 메인 대시보드 페이지"""
import streamlit as st
from datetime import datetime
from dash_data import KST, time_ago, bdg, load_gallery, get_hot_posts
from dash_charts import CHART_COLORS, svg_bar_h, svg_donut, STATUS_COLORS


def _hot_post_card(gn: str, gdf, color: str, gid: str) -> None:
    """갤러리별 인기글 카드 1개 렌더링 (TOP 1)"""
    hot = get_hot_posts(gdf, n=1)
    gal_label = f"<p class='hc-gal'>{gn}</p>"
    if hot.empty:
        st.markdown(
            f"<div class='hc'>{gal_label}"
            f"<p class='sub' style='margin:0'>수집 데이터 없음</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return
    hr    = hot.iloc[0]
    link  = str(hr.get("링크", ""))
    title = str(hr.get("제목", ""))
    date  = str(hr.get("날짜", ""))[:10]
    rec   = int(hr.get("추천수", 0))
    cmt   = int(hr.get("댓글수", 0))
    score = int(hr.get("점수", 0))
    score_badge = f"<span class='hc-score'>🏆 {score}점</span>"
    title_html = (
        f"<a href='{link}' target='_blank' style='color:#1E1E1E;text-decoration:none'>{title}</a>"
        if link.startswith("http") else title
    )
    # 갤러리명 클릭 → 해당 갤러리 페이지
    nav_key = f"hot_{gid}"
    if st.button(f"▶ {gn}", key=nav_key, use_container_width=True):
        st.session_state.page = gid
        st.rerun()
    st.markdown(
        f"<div class='hc'>"
        f"{score_badge}"
        f"<div class='hc-title'>{title_html}</div>"
        f"<div class='hc-meta'>📅 {date} &nbsp; 👍 {rec} &nbsp; 💬 {cmt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render(df, nc, ic, uc, rc, lc, counts, cfg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # ── 헤더 ──────────────────────────────────────────────────────
    hcol, rcol = st.columns([9, 1])
    with hcol:
        ann = cfg.get("announcement", "").strip()
        ann_html = (
            f"<div style='margin-top:8px;padding:6px 10px;background:#FFFCF0;"
            f"border:1px solid #FFD166;border-radius:8px;font-size:12px;font-weight:600'>"
            f"📢 {ann}</div>"
        ) if ann else ""
        st.markdown(
            "<div class='lc' style='margin-bottom:14px;padding:18px 22px'>"
            f"<p style='font-size:19px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ {cfg['app_title']}</p>"
            f"<p class='sub' style='margin:3px 0 0'>{cfg['app_subtitle']}</p>"
            f"<p class='sub' style='margin:5px 0 0'>🕐 {now} (KST)</p>"
            f"{ann_html}"
            "</div>",
            unsafe_allow_html=True,
        )
    with rcol:
        st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
        if st.button("🔄", use_container_width=True, key="rf_main", help="새로고침"):
            st.cache_data.clear()
            st.rerun()

    # ── KPI 카드 4개 (순수 B&W) ───────────────────────────────────
    total = len(df)
    errs  = sum(1 for v in df[lc] if "에러" in str(v)) if lc else 0
    tp    = sum(v for v in counts.values() if v >= 0)
    lr    = str(df[rc].iloc[0]) if rc and not df.empty else ""

    m1, m2, m3, m4 = st.columns(4)
    for col, icon, val, lbl, sub in [
        (m1, "🗂️",  f"{total}개",            "등록 갤러리",    "수집 중인 갤러리"),
        (m2, "📄",  f"{tp:,}건",              "총 수집 게시글", "전체 갤러리 합산"),
        (m3, "✅",  f"{total - errs}/{total}", "정상 갤러리",   "에러 없는 갤러리"),
        (m4, "🕐",  time_ago(lr),              "마지막 실행",   "봇 최근 실행"),
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

    # ── 갤러리 현황 테이블 + 상태 도넛 (2분할) ────────────────────
    tbl_col, chart_col = st.columns([6, 4])

    with tbl_col:
        st.markdown("<p class='sec'>📋 갤러리별 수집 현황</p>", unsafe_allow_html=True)
        hcols = st.columns([3.5, 2.5, 2, 2.5])
        for c, t in zip(hcols, ["갤러리 (클릭하면 상세)", "수집 상태", "총 게시글", "마지막 실행"]):
            c.markdown(f"<p class='th'>{t}</p>", unsafe_allow_html=True)

        for i, (_, row) in enumerate(df.iterrows()):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            gn  = str(row.get(nc, ""))
            gi  = str(row.get(ic, "")) if ic else str(i)
            rm  = str(row.get(lc, "")) if lc else ""
            lr2 = str(row.get(rc, "")) if rc else ""
            cnt = counts.get(gn, -1)

            c1, c2, c3, c4 = st.columns([3.5, 2.5, 2, 2.5])
            with c1:
                # 갤러리명 = 클릭 버튼 → 상세 페이지 이동
                st.markdown(
                    f"<div style='margin-bottom:4px'>"
                    f"<div style='display:flex;align-items:center;gap:8px'>"
                    f"<span style='display:inline-block;width:10px;height:10px;"
                    f"border-radius:50%;background:{color};"
                    f"border:1.5px solid #1E1E1E;flex-shrink:0'></span>"
                    f"<button onclick=\"\" style='background:none;border:none;cursor:pointer;"
                    f"font-weight:700;font-size:13px;color:#1E1E1E;padding:0;text-align:left'>"
                    f"{gn}</button>"
                    f"</div>"
                    f"<div class='sub' style='padding-left:18px'>{gi}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                # 실제 클릭 기능은 Streamlit button으로 처리
                if st.button(f"→ {gn} 상세보기", key=f"tbl_{gi}", use_container_width=True):
                    st.session_state.page = gi
                    st.rerun()
            with c2:
                st.markdown(f"<div class='rc' style='margin-top:0'>{bdg(rm)}</div>", unsafe_allow_html=True)
            with c3:
                cnt_txt = f"{cnt:,}건" if cnt >= 0 else "—"
                st.markdown(
                    f"<div class='rc' style='font-weight:700;margin-top:0'>📄 {cnt_txt}</div>",
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f"<div class='rc sub' style='margin-top:0'>🕐 {time_ago(lr2)}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<p class='sub' style='text-align:right;margin-top:2px'>💡 게시글 수는 5분 주기 갱신</p>",
            unsafe_allow_html=True,
        )

    with chart_col:
        # 상태 도넛
        if lc:
            sm = {"수집성공": 0, "새글없음": 0, "에러": 0, "미실행": 0}
            for v in df[lc]:
                s = str(v)
                if "개 수집" in s:      sm["수집성공"] += 1
                elif "새 글 없음" in s: sm["새글없음"] += 1
                elif "에러" in s:       sm["에러"]     += 1
                else:                   sm["미실행"]   += 1
            donut = svg_donut({k: v for k, v in sm.items() if v > 0})
            legend_parts = []
            for k, v in sm.items():
                if v > 0:
                    color = STATUS_COLORS.get(k, "#999")
                    legend_parts.append(
                        f"<span style='display:inline-flex;align-items:center;gap:5px;"
                        f"margin:3px 8px 3px 0;font-size:12px'>"
                        f"<span style='width:9px;height:9px;flex-shrink:0;border-radius:50%;"
                        f"background:{color};border:1.5px solid #1E1E1E'></span>"
                        f"{k} {v}</span>"
                    )
            legend = "".join(legend_parts)
            st.markdown(
                "<div class='lc'>"
                "<p class='ctitle'>수집 상태 분포</p>"
                f"<div style='display:flex;justify-content:center'>{donut}</div>"
                f"<div style='text-align:center;margin-top:10px'>{legend}</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        # 갤러리별 수집량 바 차트
        bar_svg = svg_bar_h({k: max(v, 0) for k, v in counts.items()}) if counts else ""
        if bar_svg:
            st.markdown(
                "<div class='lc'>"
                "<p class='ctitle'>갤러리별 수집 게시글</p>"
                f"{bar_svg}"
                "</div>",
                unsafe_allow_html=True,
            )

    # ── 갤러리별 인기글 — PC 3열 그리드 ─────────────────────────
    st.markdown("<p class='sec'>🔥 갤러리별 인기글 TOP 1</p>", unsafe_allow_html=True)
    st.caption("추천수×2 + 댓글수 점수 기준 | 갤러리명 버튼 클릭 시 상세 페이지 이동")

    gallery_rows = [(str(r.get(nc, "")),
                     str(r.get(ic, "")) if ic else str(i),
                     str(r.get(uc, "")) if uc else "")
                    for i, (_, r) in enumerate(df.iterrows())]
    valid = [(gn, gid, su) for gn, gid, su in gallery_rows if su.startswith("http")]

    N_COLS = 3
    for batch_start in range(0, len(valid), N_COLS):
        batch = valid[batch_start:batch_start + N_COLS]
        cols  = st.columns(N_COLS)
        for col, (gn, gid, su) in zip(cols, batch):
            color = CHART_COLORS[gallery_rows.index((gn, gid, su)) % len(CHART_COLORS)]
            with col:
                gdf = load_gallery(su)
                _hot_post_card(gn, gdf, color, gid)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:20px;padding-top:12px;"
        f"border-top:1px solid #E5E5E5'>"
        f"<span class='sub'>PM : {cfg['pm_name']} &nbsp;|&nbsp; DC-Pickaxe {cfg['app_version']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

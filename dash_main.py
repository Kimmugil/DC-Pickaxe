"""DC-Pickaxe 메인 대시보드 페이지"""
import streamlit as st
from datetime import datetime
from dash_data import KST, time_ago, bdg, find_col, load_gallery, get_hot_posts
from dash_charts import CHART_COLORS, svg_bar_h, svg_donut, STATUS_COLORS


def render(df, nc, ic, uc, rc, lc, counts, cfg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # ── 헤더 ──────────────────────────────────────────────────────
    hcol, rcol = st.columns([9, 1])
    with hcol:
        st.markdown(
            "<div class='lc' style='border-left:5px solid #FFD166;border-top-left-radius:6px;border-bottom-left-radius:6px;margin-bottom:14px'>"
            f"<p style='font-size:20px;font-weight:900;color:#1E1E1E;margin:0'>⛏️ {cfg['app_title']}</p>"
            f"<p class='sub' style='margin:4px 0 0'>{cfg['app_subtitle']}</p>"
            f"<p class='sub' style='margin:6px 0 0'>🕐 현재 시각 (KST) &nbsp;<strong>{now}</strong></p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with rcol:
        st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
        if st.button("🔄", use_container_width=True, key="rf_main", help="새로고침"):
            st.cache_data.clear()
            st.rerun()

    # 공지 배너 (config 탭에서 announcement 값 설정 시 표시)
    ann = cfg.get("announcement", "").strip()
    if ann:
        st.markdown(
            f"<div class='lc' style='background:#FFFCF0;border-color:#FFD166;padding:12px 18px;margin-bottom:10px'>"
            f"<span style='font-size:13px;font-weight:600'>📢 {ann}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── KPI 카드 4개 ───────────────────────────────────────────────
    total = len(df)
    errs  = sum(1 for v in df[lc] if "에러" in str(v)) if lc else 0
    tp    = sum(v for v in counts.values() if v >= 0)
    lr    = str(df[rc].iloc[0]) if rc and not df.empty else ""

    m1, m2, m3, m4 = st.columns(4)
    for col, accent, icon, val, lbl, sub in [
        (m1, "#FFD166", "🗂️",  f"{total}개",           "등록 갤러리",     "수집 중인 갤러리"),
        (m2, "#82C29A", "📄",  f"{tp:,}건",              "총 수집 게시글",  "전체 갤러리 합산"),
        (m3, "#6DC2FF", "✅",  f"{total - errs}/{total}", "정상 갤러리",     "에러 없는 갤러리"),
        (m4, "#FF9F9F", "🕐",  time_ago(lr),              "마지막 실행",     "봇 최근 실행 시각"),
    ]:
        with col:
            st.markdown(
                f"<div class='mc' style='border-top:3px solid {accent}'>"
                f"<div style='font-size:20px;margin-bottom:6px'>{icon}</div>"
                f"<div class='mval'>{val}</div>"
                f"<div class='mlbl'>{lbl}</div>"
                f"<div class='msub'>{sub}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── 차트 ───────────────────────────────────────────────────────
    ch1, ch2 = st.columns([3, 2])
    with ch1:
        bar_svg = svg_bar_h({k: max(v, 0) for k, v in counts.items()}) if counts else ""
        st.markdown(
            "<div class='lc'>"
            "<p class='ctitle'>갤러리별 수집 게시글 수</p>"
            f"{bar_svg}"
            "</div>",
            unsafe_allow_html=True,
        )
    with ch2:
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
                        f"margin:3px 8px 3px 0;font-size:12px;color:#1E1E1E'>"
                        f"<span style='width:9px;height:9px;border-radius:50%;"
                        f"background:{color};border:1px solid #1E1E1E;flex-shrink:0'></span>"
                        f"{k} {v}</span>"
                    )
            legend = "".join(legend_parts)
            st.markdown(
                "<div class='lc'>"
                "<p class='ctitle'>수집 상태 분포</p>"
                f"<div style='display:flex;align-items:center;justify-content:center'>{donut}</div>"
                f"<div style='text-align:center;margin-top:10px'>{legend}</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    # ── 갤러리별 수집 현황 테이블 ──────────────────────────────────
    st.markdown("<p class='sec'>📋 갤러리별 수집 현황</p>", unsafe_allow_html=True)
    hcols = st.columns([3, 2.5, 2, 2.2, 1.6])
    for c, t in zip(hcols, ["갤러리", "수집 상태", "총 게시글", "마지막 실행", "바로가기"]):
        c.markdown(f"<p class='th'>{t}</p>", unsafe_allow_html=True)

    for i, (_, row) in enumerate(df.iterrows()):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        gn  = str(row.get(nc, ""))
        gi  = str(row.get(ic, "")) if ic else ""
        rm  = str(row.get(lc, "")) if lc else ""
        lr2 = str(row.get(rc, "")) if rc else ""
        su  = str(row.get(uc, "")) if uc else ""
        cnt = counts.get(gn, -1)
        c1, c2, c3, c4, c5 = st.columns([3, 2.5, 2, 2.2, 1.6])
        with c1:
            st.markdown(
                f"<div class='rc' style='border-left:4px solid {color}'>"
                f"<div style='font-weight:700;font-size:13px'>{gn}</div>"
                f"<div class='sub'>{gi}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='rc'>{bdg(rm)}</div>", unsafe_allow_html=True)
        with c3:
            cnt_txt = f"{cnt:,}건" if cnt >= 0 else "집계 중"
            st.markdown(
                f"<div class='rc' style='font-weight:700'>📄 {cnt_txt}</div>",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f"<div class='rc sub'>🕐 {time_ago(lr2)}</div>",
                unsafe_allow_html=True,
            )
        with c5:
            if su.startswith("http"):
                st.link_button("시트 →", su, use_container_width=True)

    st.markdown(
        "<p class='sub' style='text-align:right;margin-top:4px'>"
        "💡 총 게시글 수는 5분 주기 갱신</p>",
        unsafe_allow_html=True,
    )

    # ── 갤러리별 인기글 미리보기 (접기/펼치기) ────────────────────
    if uc:
        with st.expander("🔥 갤러리별 인기글 미리보기 (펼치기)"):
            st.caption("각 갤러리에서 추천수×2 + 댓글수 점수 기준 TOP 3를 표시합니다.")
            for i, (_, row) in enumerate(df.iterrows()):
                gn = str(row.get(nc, ""))
                su = str(row.get(uc, "")) if uc else ""
                if not su.startswith("http"):
                    continue
                color = CHART_COLORS[i % len(CHART_COLORS)]
                gdf = load_gallery(su)
                hot = get_hot_posts(gdf, n=3)
                st.markdown(
                    f"<p style='font-size:13px;font-weight:700;margin:14px 0 6px;"
                    f"border-left:3px solid {color};padding-left:8px'>{gn}</p>",
                    unsafe_allow_html=True,
                )
                if hot.empty:
                    st.caption("수집된 게시글이 없습니다.")
                    continue
                for _, hr in hot.iterrows():
                    link = str(hr.get("링크", ""))
                    title = str(hr.get("제목", ""))
                    date  = str(hr.get("날짜", ""))[:10]
                    rec   = int(hr.get("추천수", 0))
                    cmt   = int(hr.get("댓글수", 0))
                    href_html = (
                        f"<a href='{link}' target='_blank'"
                        f" style='color:#1E1E1E;text-decoration:none'>{title}</a>"
                        if link.startswith("http") else title
                    )
                    st.markdown(
                        f"<div class='hc'>"
                        f"<div class='hc-title'>{href_html}</div>"
                        f"<div class='hc-meta'>📅 {date} &nbsp;👍 추천 {rec} &nbsp;💬 댓글 {cmt}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:16px'>"
        f"<span class='sub'>시스템 총괄 PM : {cfg['pm_name']} &nbsp;|&nbsp; DC-Pickaxe {cfg['app_version']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

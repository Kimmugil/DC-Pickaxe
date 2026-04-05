"""DC-Pickaxe 메인 대시보드 페이지"""
import re
import pandas as pd
import streamlit as st
from datetime import datetime
from dash_data import KST, time_ago, load_gallery, get_hot_posts
from dash_charts import CHART_COLORS, svg_multi_line_daily


def _dc_url(gallery_id, gallery_type):
    """DC Inside 갤러리 목록 URL 반환"""
    prefix_map = {"일반": "board", "미니": "mini/board"}
    prefix = prefix_map.get(str(gallery_type).strip(), "mgallery/board")
    return f"https://gall.dcinside.com/{prefix}/lists/?id={gallery_id}"


def render(df, nc, ic, uc, rc, lc, tc, counts, cfg):
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

    # ── 히어로 카드 ────────────────────────────────────────────────
    ann = cfg.get("announcement", "").strip()
    ann_html = (
        f"<div style='margin:10px 0 0;padding:7px 12px;background:#FFFCF0;"
        f"border:1px solid #FFD166;border-radius:8px;font-size:12px;font-weight:600'>"
        f"📢 {ann}</div>"
    ) if ann else ""

    kpi_data = [
        (f"{tp:,}건",       cfg.get("kpi_total_posts", "총 수집 게시글"), "#F0FAF3", True),
        (f"{this_run:,}건", cfg.get("kpi_this_run",    "이번 수집량"),    "#FFFCF0", True),
        (time_ago(lr),      cfg.get("kpi_last_run",    "마지막 실행"),    "#EFF8FF", False),
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
        "<div class='lc' style='margin-bottom:24px;padding:0;overflow:hidden'>"
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

    # ── 갤러리 데이터 사전 로드 (차트 + 인기글 공용) ───────────────
    gallery_dfs: dict[str, pd.DataFrame] = {}
    if uc:
        for _, row in df.iterrows():
            su  = str(row.get(uc, ""))
            gn  = str(row.get(nc, ""))
            if su.startswith("http"):
                gallery_dfs[gn] = load_gallery(su)

    # ── 일자별 추이 SVG 차트 ───────────────────────────────────────
    series = []
    for i, (_, row) in enumerate(df.iterrows()):
        gn    = str(row.get(nc, ""))
        color = CHART_COLORS[i % len(CHART_COLORS)]
        gdf   = gallery_dfs.get(gn, pd.DataFrame())
        if not gdf.empty and "날짜_date" in gdf.columns:
            daily = {
                str(d): int(v)
                for d, v in gdf.groupby("날짜_date").size().items()
            }
            series.append((gn, color, daily))

    if series:
        chart_svg = svg_multi_line_daily(series)
        st.markdown(
            "<div class='lc' style='padding:18px 22px;margin-bottom:20px'>"
            f"<p class='ctitle' style='margin-bottom:10px'>"
            f"{cfg.get('title_trend', '📈 갤러리별 게시글 추이 (최근 30일)')}</p>"
            f"{chart_svg}"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── 섹션 타이틀 ───────────────────────────────────────────────
    st.markdown(
        f"<p class='sec' style='margin-top:4px;margin-bottom:12px'>"
        f"{cfg.get('title_table', '📋 갤러리별 수집 현황')}</p>",
        unsafe_allow_html=True,
    )

    # ── 갤러리 카드 (HTML 일괄 빌드 → 그리드 렌더) ────────────────
    lbl_link   = cfg.get("btn_gallery_link", "📊 갤러리 바로가기")
    lbl_detail = cfg.get("btn_detail",        "→ 수집 상세 보기")
    lbl_total  = cfg.get("kpi_card_total",    "총 게시글")
    lbl_run    = cfg.get("kpi_card_this_run", "이번 수집")
    lbl_last   = cfg.get("kpi_card_last_run", "마지막 실행")
    lbl_hot    = cfg.get("label_hot_prefix",  "🔥 인기글")
    lbl_nodata = cfg.get("label_no_data",     "데이터 없음")

    cards_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        gn    = str(row.get(nc, ""))
        gi    = str(row.get(ic, "")) if ic else str(i)
        rm    = str(row.get(lc, "")) if lc else ""
        lr2   = str(row.get(rc, "")) if rc else ""
        su    = str(row.get(uc, "")) if uc else ""
        gtype = str(row.get(tc, "마이너")) if tc else "마이너"
        cnt   = counts.get(gn, -1)
        cnt_txt = f"{cnt:,}건" if cnt >= 0 else "—"

        # 이번 수집량 파싱
        m_run = re.search(r"(\d+)개", rm)
        if m_run:
            run_n = int(m_run.group(1))
            this_run_txt = "새 글 없음" if run_n == 0 else f"{run_n:,}건"
        else:
            this_run_txt = "—"

        # 인기글
        hot_content = f"<span class='sub'>{lbl_nodata}</span>"
        hot_period  = "24시간 내"
        gdf = gallery_dfs.get(gn, pd.DataFrame())
        if not gdf.empty:
            hot, period = get_hot_posts(gdf, n=1)
            hot_period = period
            if not hot.empty:
                hr     = hot.iloc[0]
                link   = str(hr.get("링크", ""))
                title  = str(hr.get("제목", ""))
                rec    = int(hr.get("추천수", 0))
                cmt    = int(hr.get("댓글수", 0))
                t_short = title[:30] + "…" if len(title) > 30 else title
                t_tag   = (
                    f"<a href='{link}' target='_blank'"
                    f" style='color:#1E1E1E;text-decoration:none;font-weight:600'>"
                    f"{t_short}</a>"
                    if link.startswith("http") else
                    f"<span style='font-weight:600'>{t_short}</span>"
                )
                hot_content = (
                    f"<div style='font-size:13px;line-height:1.5'>🔥 {t_tag}</div>"
                    f"<div class='sub' style='margin-top:4px'>👍 {rec} &nbsp; 💬 {cmt}</div>"
                )

        dot = (
            f"<span style='display:inline-block;width:10px;height:10px;"
            f"border-radius:50%;background:{color};border:1.5px solid #1E1E1E;"
            f"flex-shrink:0;vertical-align:middle;margin-right:6px'></span>"
        )

        # 버튼: 갤러리 바로가기 → DC Inside URL
        dc_link = _dc_url(gi, gtype)
        link_btn = (
            f"<a href='{dc_link}' target='_blank'"
            f" style='display:flex;align-items:center;justify-content:center;"
            f"flex:1;padding:11px 6px;border-right:1.5px solid #1E1E1E;"
            f"font-size:13px;font-weight:600;color:#1E1E1E;text-decoration:none;"
            f"background:#FFFFFF'>{lbl_link}</a>"
        )
        detail_btn = (
            f"<a href='?gallery={gi}'"
            f" style='display:flex;align-items:center;justify-content:center;"
            f"flex:1;padding:11px 6px;"
            f"font-size:13px;font-weight:600;color:#1E1E1E;text-decoration:none;"
            f"background:#FFFFFF'>{lbl_detail}</a>"
        )

        cards_html += (
            f"<div class='lc' style='padding:0;overflow:hidden;margin-bottom:0'>"
            # 헤더
            f"<div style='padding:14px 18px 10px'>"
            f"<div style='display:flex;align-items:center;flex-wrap:wrap;gap:6px'>"
            f"<span style='font-size:15px;font-weight:900'>{dot}{gn}</span>"
            f"</div>"
            f"<p class='sub' style='margin:5px 0 0;padding-left:16px'>{gi}</p>"
            f"</div>"
            # KPI 3블록
            f"<div style='display:flex;border-top:1.5px solid #1E1E1E'>"
            f"<div style='flex:1;padding:10px 12px;background:#F0FAF3;"
            f"border-right:1.5px solid #1E1E1E;min-width:0'>"
            f"<div style='font-size:17px;font-weight:900;color:#1E1E1E'>{cnt_txt}</div>"
            f"<div style='font-size:10px;color:#757575;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.4px;margin-top:3px'>{lbl_total}</div>"
            f"</div>"
            f"<div style='flex:1;padding:10px 12px;background:#FFFCF0;"
            f"border-right:1.5px solid #1E1E1E;min-width:0'>"
            f"<div style='font-size:17px;font-weight:900;color:#1E1E1E'>{this_run_txt}</div>"
            f"<div style='font-size:10px;color:#757575;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.4px;margin-top:3px'>{lbl_run}</div>"
            f"</div>"
            f"<div style='flex:1;padding:10px 12px;background:#EFF8FF;min-width:0'>"
            f"<div style='font-size:17px;font-weight:900;color:#1E1E1E'>{time_ago(lr2)}</div>"
            f"<div style='font-size:10px;color:#757575;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.4px;margin-top:3px'>{lbl_last}</div>"
            f"</div>"
            f"</div>"
            # 인기글 영역
            f"<div style='border-top:1.5px solid #1E1E1E;padding:10px 14px;background:#FFFFFF'>"
            f"<div style='font-size:10px;font-weight:700;color:#757575;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px'>"
            f"{lbl_hot} ({hot_period} 기준)</div>"
            f"{hot_content}"
            f"</div>"
            # 버튼 행
            f"<div style='display:flex;border-top:1.5px solid #1E1E1E'>"
            f"{link_btn}{detail_btn}"
            f"</div>"
            f"</div>"
        )

    st.markdown(
        f"<div class='gallery-grid'>{cards_html}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<p class='sub' style='text-align:right;margin-top:2px'>"
        f"💡 {cfg.get('collection_note', '봇 실행 시 갱신 (1시간 주기)')}</p>",
        unsafe_allow_html=True,
    )

    # ── 푸터 ──────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:right;margin-top:20px;padding-top:12px;"
        f"border-top:1px solid #E5E5E5'>"
        f"<span class='sub'>PM : {cfg['pm_name']} &nbsp;|&nbsp; "
        f"DC-Pickaxe {cfg['app_version']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

"""DC-Pickaxe SVG Chart Components — Clean Line Bento"""
import math

CHART_COLORS = [
    "#FFD166", "#82C29A", "#FF9F9F", "#6DC2FF",
    "#B5B2FF", "#FFBE7D", "#A8E6CF", "#FFD3B6",
]


def _pts(values, w, h, pad=16):
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(values)
    return [
        (
            pad + (i / max(n - 1, 1)) * (w - 2 * pad),
            pad + (1 - (v - vmin) / (vmax - vmin)) * (h - 2 * pad),
        )
        for i, v in enumerate(values)
    ]


def svg_line_area(values, width=560, height=130,
                  line_color="#1E1E1E", fill_color="#82C29A", svg_id="a"):
    if len(values) < 2:
        return ""
    pts = _pts(values, width, height)
    pad = 16
    path = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        cx = (x0 + x1) / 2
        path += f" C {cx:.1f},{y0:.1f} {cx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    area = (
        path
        + f" L {pts[-1][0]:.1f},{height - pad:.1f}"
        + f" L {pts[0][0]:.1f},{height - pad:.1f} Z"
    )
    uid = f"lg_{svg_id}"
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>"
        f"<defs><linearGradient id='{uid}' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0%' stop-color='{fill_color}' stop-opacity='.30'/>"
        f"<stop offset='100%' stop-color='{fill_color}' stop-opacity='.03'/>"
        f"</linearGradient></defs>"
        f"<path d='{area}' fill='url(#{uid})' stroke='none'/>"
        f"<path d='{path}' fill='none' stroke='{line_color}' stroke-width='1.5'"
        f" stroke-linecap='round' stroke-linejoin='round' vector-effect='non-scaling-stroke'/>"
        f"</svg>"
    )


def _robust_vmax(values):
    """이상치(백필 대량 수집일 등)가 Y축을 지배하지 않도록 95th 퍼센타일 기반 상한 계산."""
    nz = sorted(v for v in values if v > 0)
    if not nz:
        return 1
    raw_max = nz[-1]
    if len(nz) < 4:
        return raw_max
    p95 = nz[int(len(nz) * 0.95)]
    # 최댓값이 95th 퍼센타일의 3배 이상이면 이상치 → 95th 퍼센타일로 캡
    return p95 if raw_max > p95 * 3 else raw_max


def svg_bar_daily(dates, values, width=580, height=160, bar_color="#FFD166"):
    if not values:
        return ""
    n = len(values)
    vmax = _robust_vmax(values)
    pl, pr, pt, pb = 8, 8, 32, 28  # pt=32: 바 위 수치 라벨 공간 확보
    cw = (width - pl - pr) / n
    bw = max(cw * 0.65, 2)
    ch = height - pt - pb
    out = ""
    for i, (d, v) in enumerate(zip(dates, values)):
        cx = pl + i * cw + cw / 2          # 바 중심 X
        x  = cx - bw / 2
        bh = min(v / vmax, 1.0) * ch
        y  = pt + ch - bh
        # 막대
        if bh > 0:
            out += (
                f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}'"
                f" rx='3' fill='{bar_color}' stroke='#1E1E1E' stroke-width='1.5'"
                f" vector-effect='non-scaling-stroke'/>"
            )
        # 수치 라벨: 바 위에 세로(회전) 텍스트
        if v > 0:
            label_y = y - 3           # 바 바로 위
            val_str = f"{v:,}"
            out += (
                f"<text"
                f" transform='rotate(-90,{cx:.1f},{label_y:.1f})'"
                f" x='{cx:.1f}' y='{label_y:.1f}'"
                f" text-anchor='start'"
                f" font-size='8' font-weight='600' fill='#555555'>{val_str}</text>"
            )
        # X축 날짜 라벨 (간격 조절)
        if n <= 14 or i % max(n // 6, 1) == 0:
            lbl = str(d)[5:] if isinstance(d, str) and len(str(d)) >= 7 else str(d)
            out += (
                f"<text x='{cx:.1f}' y='{height - 6:.1f}'"
                f" text-anchor='middle' font-size='9' fill='#757575'>{lbl}</text>"
            )
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{out}</svg>"
    )


def svg_multi_line_daily(series, width=880, height=210):
    """
    갤러리별 일자별 게시글 수 멀티라인 SVG 차트.
    series: list of (name, color, {date_str: int})

    각 시리즈를 자신의 최댓값 기준으로 독립 정규화(0~100%)하여
    규모 차이가 큰 갤러리들도 추이 패턴을 함께 비교할 수 있게 함.
    라인 끝에 실제 최고값 라벨을 표시해 절대 규모도 파악 가능.
    """
    if not series:
        return ""

    # 모든 날짜 수집 → 최근 30일
    all_dates = sorted(set(d for _, _, data in series for d in data.keys()))
    if len(all_dates) < 2:
        return ""
    all_dates = all_dates[-30:]
    n = len(all_dates)

    legend_h = 24
    pl, pr, pt, pb = 14, 80, legend_h + 10, 26  # pr=80 → 우측에 최고값 라벨 공간
    draw_w = width - pl - pr
    draw_h = height - pt - pb

    def xy(i, v, series_vmax):
        x = pl + (i / max(n - 1, 1)) * draw_w
        ratio = min(v / series_vmax, 1.0) if series_vmax > 0 else 0
        y = pt + draw_h * (1.0 - ratio)
        return x, y

    out = ""

    # 가로 그리드 라인
    for level in (0.25, 0.5, 0.75, 1.0):
        gy = pt + draw_h * (1.0 - level)
        out += (
            f"<line x1='{pl}' y1='{gy:.1f}' x2='{pl + draw_w}' y2='{gy:.1f}'"
            f" stroke='#EDEDEE' stroke-width='1'/>"
        )

    # 각 시리즈 라인 — 시리즈별 독립 vmax
    for name, color, data in series:
        vals = [data.get(d, 0) for d in all_dates]
        if all(v == 0 for v in vals):
            continue
        series_vmax = _robust_vmax(vals) or 1
        pts = [xy(i, v, series_vmax) for i, v in enumerate(vals)]
        path = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
        for i in range(1, len(pts)):
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            cx = (x0 + x1) / 2
            path += f" C {cx:.1f},{y0:.1f} {cx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
        out += (
            f"<path d='{path}' fill='none' stroke='{color}'"
            f" stroke-width='2' stroke-linecap='round' stroke-linejoin='round'"
            f" vector-effect='non-scaling-stroke'/>"
        )
        # 마지막 데이터 포인트 원 + 최고값 라벨
        lx, ly = pts[-1]
        out += (
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='3'"
            f" fill='{color}' stroke='#1E1E1E' stroke-width='1'"
            f" vector-effect='non-scaling-stroke'/>"
        )
        # 우측 라벨: 최근일 값 / 최고값
        last_val = vals[-1]
        label_y = max(pt + 8, min(ly, pt + draw_h - 4))  # 상하 클리핑
        out += (
            f"<text x='{lx + 7:.1f}' y='{label_y:.1f}'"
            f" font-size='9' fill='{color}' font-weight='700'"
            f" dominant-baseline='middle'>{last_val:,}건</text>"
        )

    # 베이스라인
    base_y = pt + draw_h
    out += (
        f"<line x1='{pl}' y1='{base_y:.1f}' x2='{pl + draw_w}' y2='{base_y:.1f}'"
        f" stroke='#CCCCCC' stroke-width='1'/>"
    )

    # X축 날짜 라벨
    label_indices = [0]
    step = max(n // 5, 1)
    label_indices += list(range(step, n - 1, step))
    if (n - 1) not in label_indices:
        label_indices.append(n - 1)
    for i in label_indices:
        x = pl + (i / max(n - 1, 1)) * draw_w
        lbl = all_dates[i][5:]  # MM-DD
        out += (
            f"<text x='{x:.1f}' y='{height - 6}'"
            f" text-anchor='middle' font-size='9' fill='#AAAAAA'>{lbl}</text>"
        )

    # 범례 (상단, 균등 배분) — 최고값 포함
    ns = len(series)
    slot_w = (width - pl - 10) / max(ns, 1)
    for idx, (name, color, data) in enumerate(series):
        lx = pl + idx * slot_w
        short = (name[:5] + "…") if len(name) > 5 else name
        vals_all = [data.get(d, 0) for d in all_dates]
        peak = max(vals_all) if vals_all else 0
        out += (
            f"<circle cx='{lx + 5:.1f}' cy='12' r='4.5' fill='{color}'"
            f" stroke='#1E1E1E' stroke-width='1.2' vector-effect='non-scaling-stroke'/>"
            f"<text x='{lx + 14:.1f}' y='14' font-size='10'"
            f" fill='#1E1E1E' font-weight='600'>{short}</text>"
            f"<text x='{lx + 14:.1f}' y='23' font-size='8'"
            f" fill='#AAAAAA'>최대 {peak:,}건</text>"
        )

    # 우상단 안내 텍스트
    out += (
        f"<text x='{width - 4}' y='{pt - 2}'"
        f" text-anchor='end' font-size='8' fill='#CCCCCC'"
        f" font-style='italic'>각 갤러리 독립 스케일</text>"
    )

    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{out}</svg>"
    )

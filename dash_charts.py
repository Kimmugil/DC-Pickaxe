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
    pl, pr, pt, pb = 8, 8, 20, 28
    cw = (width - pl - pr) / n
    bw = max(cw * 0.65, 2)
    ch = height - pt - pb
    out = ""
    for i, (d, v) in enumerate(zip(dates, values)):
        x = pl + i * cw + (cw - bw) / 2
        bh = min(v / vmax, 1.0) * ch  # vmax 초과 시 꽉 찬 바로 표시
        y = pt + ch - bh
        out += (
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}'"
            f" rx='3' fill='{bar_color}' stroke='#1E1E1E' stroke-width='1.5'"
            f" vector-effect='non-scaling-stroke'/>"
        )
        if n <= 14 or i % max(n // 6, 1) == 0:
            lbl = str(d)[5:] if isinstance(d, str) and len(str(d)) >= 7 else str(d)
            out += (
                f"<text x='{x + bw / 2:.1f}' y='{height - 6:.1f}'"
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
    """
    if not series:
        return ""

    # 모든 날짜 수집 → 최근 30일
    all_dates = sorted(set(d for _, _, data in series for d in data.keys()))
    if len(all_dates) < 2:
        return ""
    all_dates = all_dates[-30:]
    n = len(all_dates)

    all_vals = [data.get(d, 0) for _, _, data in series for d in all_dates]
    vmax = _robust_vmax(all_vals) or 1

    legend_h = 24
    pl, pr, pt, pb = 14, 14, legend_h + 10, 26
    draw_w = width - pl - pr
    draw_h = height - pt - pb

    def xy(i, v):
        x = pl + (i / max(n - 1, 1)) * draw_w
        y = pt + draw_h * (1.0 - min(v / vmax, 1.0))  # vmax 초과 시 상단 고정
        return x, y

    out = ""

    # 가로 그리드 라인
    for level in (0.25, 0.5, 0.75, 1.0):
        gy = pt + draw_h * (1.0 - level)
        out += (
            f"<line x1='{pl}' y1='{gy:.1f}' x2='{width - pr}' y2='{gy:.1f}'"
            f" stroke='#EDEDEE' stroke-width='1'/>"
        )

    # 각 시리즈 라인
    for name, color, data in series:
        vals = [data.get(d, 0) for d in all_dates]
        if all(v == 0 for v in vals):
            continue
        pts = [xy(i, v) for i, v in enumerate(vals)]
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
        # 마지막 데이터 포인트 원
        lx, ly = pts[-1]
        out += (
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='3'"
            f" fill='{color}' stroke='#1E1E1E' stroke-width='1'"
            f" vector-effect='non-scaling-stroke'/>"
        )

    # 베이스라인
    base_y = pt + draw_h
    out += (
        f"<line x1='{pl}' y1='{base_y:.1f}' x2='{width - pr}' y2='{base_y:.1f}'"
        f" stroke='#CCCCCC' stroke-width='1'/>"
    )

    # X축 날짜 라벨
    label_indices = [0]
    step = max(n // 5, 1)
    label_indices += list(range(step, n - 1, step))
    if (n - 1) not in label_indices:
        label_indices.append(n - 1)
    for i in label_indices:
        x, _ = xy(i, 0)
        lbl = all_dates[i][5:]  # MM-DD
        out += (
            f"<text x='{x:.1f}' y='{height - 6}'"
            f" text-anchor='middle' font-size='9' fill='#AAAAAA'>{lbl}</text>"
        )

    # 범례 (상단, 균등 배분)
    ns = len(series)
    slot_w = (width - 2 * pl) / max(ns, 1)
    for idx, (name, color, _) in enumerate(series):
        lx = pl + idx * slot_w
        short = (name[:5] + "…") if len(name) > 5 else name
        out += (
            f"<circle cx='{lx + 5:.1f}' cy='12' r='4.5' fill='{color}'"
            f" stroke='#1E1E1E' stroke-width='1.2' vector-effect='non-scaling-stroke'/>"
            f"<text x='{lx + 14:.1f}' y='16' font-size='10'"
            f" fill='#1E1E1E' font-weight='600'>{short}</text>"
        )

    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{out}</svg>"
    )

"""DC-Pickaxe SVG Chart Components — Clean Line Bento"""
import math

CHART_COLORS = [
    "#FFD166", "#82C29A", "#FF9F9F", "#6DC2FF",
    "#B5B2FF", "#FFBE7D", "#A8E6CF", "#FFD3B6",
]

STATUS_COLORS = {
    "수집성공": "#82C29A",
    "새글없음": "#6DC2FF",
    "에러":     "#FF9F9F",
    "미실행":   "#E0E0E0",
}


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


def svg_bar_h(data, width=480, height=200):
    if not data:
        return ""
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    n = len(items)
    vmax = max(v for _, v in items) or 1
    row_h = (height - 10) / n
    bar_area = width - 110
    out = ""
    for i, (label, val) in enumerate(items):
        y = i * row_h + row_h * 0.15
        bh = row_h * 0.55
        bw = (val / vmax) * bar_area
        color = CHART_COLORS[i % len(CHART_COLORS)]
        short = (label[:7] + "…") if len(label) > 8 else label
        out += (
            f"<rect x='104' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}'"
            f" rx='4' fill='{color}' stroke='#1E1E1E' stroke-width='1.5'"
            f" vector-effect='non-scaling-stroke'/>"
            f"<text x='100' y='{y + bh * 0.78:.1f}' text-anchor='end'"
            f" font-size='12' fill='#1E1E1E' font-weight='500'>{short}</text>"
            f"<text x='{104 + bw + 6:.1f}' y='{y + bh * 0.78:.1f}'"
            f" font-size='11' fill='#757575'>{val:,}</text>"
        )
    return (
        f"<svg width='100%' viewBox='0 0 {width} {height}'"
        f" xmlns='http://www.w3.org/2000/svg'>{out}</svg>"
    )


def svg_bar_daily(dates, values, width=580, height=160, bar_color="#FFD166"):
    if not values:
        return ""
    n = len(values)
    vmax = max(values) or 1
    pl, pr, pt, pb = 8, 8, 20, 28
    cw = (width - pl - pr) / n
    bw = max(cw * 0.65, 2)
    ch = height - pt - pb
    out = ""
    for i, (d, v) in enumerate(zip(dates, values)):
        x = pl + i * cw + (cw - bw) / 2
        bh = (v / vmax) * ch
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


def svg_donut(data, size=170):
    if not data or sum(data.values()) == 0:
        return ""
    total = sum(data.values())
    cx = cy = size / 2
    ro = size * 0.40
    ri = size * 0.24
    angle = -90.0
    slices = ""
    for label, val in data.items():
        if val == 0:
            continue
        sweep = (val / total) * 360
        end = angle + sweep
        sr = math.radians(angle)
        er = math.radians(end)
        ox1 = cx + ro * math.cos(sr)
        oy1 = cy + ro * math.sin(sr)
        ox2 = cx + ro * math.cos(er)
        oy2 = cy + ro * math.sin(er)
        ix1 = cx + ri * math.cos(er)
        iy1 = cy + ri * math.sin(er)
        ix2 = cx + ri * math.cos(sr)
        iy2 = cy + ri * math.sin(sr)
        la = 1 if sweep > 180 else 0
        c = STATUS_COLORS.get(label, "#CCCCCC")
        dp = (
            f"M {ox1:.1f} {oy1:.1f} A {ro:.1f} {ro:.1f} 0 {la} 1 {ox2:.1f} {oy2:.1f}"
            f" L {ix1:.1f} {iy1:.1f} A {ri:.1f} {ri:.1f} 0 {la} 0 {ix2:.1f} {iy2:.1f} Z"
        )
        slices += (
            f"<path d='{dp}' fill='{c}' stroke='#1E1E1E'"
            f" stroke-width='1' vector-effect='non-scaling-stroke'/>"
        )
        angle = end
    slices += (
        f"<text x='{cx:.0f}' y='{cy - 4:.0f}' text-anchor='middle'"
        f" font-size='18' font-weight='800' fill='#1E1E1E'>{total}</text>"
        f"<text x='{cx:.0f}' y='{cy + 14:.0f}' text-anchor='middle'"
        f" font-size='10' fill='#757575'>전체</text>"
    )
    return (
        f"<svg width='{size}' height='{size}' viewBox='0 0 {size} {size}'"
        f" xmlns='http://www.w3.org/2000/svg'>{slices}</svg>"
    )

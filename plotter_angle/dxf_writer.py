import math

def _dxf_header():
    return [
        "0","SECTION","2","HEADER",
        "9","$ACADVER","1","AC1015",
        "0","ENDSEC",
        "0","SECTION","2","TABLES",
        "0","TABLE","2","LAYER","70","5",
        "0","LAYER","2","BOUNDARY","70","0","62","7","6","CONTINUOUS",
        "0","LAYER","2","CURVE","70","0","62","1","6","CONTINUOUS",
        "0","LAYER","2","ANGLE","70","0","62","2","6","CONTINUOUS",
        "0","LAYER","2","BEARING_DISTANCE","70","0","62","3","6","CONTINUOUS",
        "0","LAYER","2","BD_TICKS","70","0","62","3","6","CONTINUOUS",
        "0","ENDTAB",
        "0","ENDSEC",
        "0","SECTION","2","ENTITIES"
    ]

def _dxf_footer():
    return ["0","ENDSEC","0","EOF"]

def _line(layer, x1, y1, x2, y2):
    return [
        "0","LINE","8",layer,
        "10",f"{x1:.6f}","20",f"{y1:.6f}","30","0.0",
        "11",f"{x2:.6f}","21",f"{y2:.6f}","31","0.0",
    ]

def _polyline(layer, pts):
    out = ["0","POLYLINE","8",layer,"66","1","70","0"]
    for (x,y) in pts:
        out += ["0","VERTEX","8",layer,"10",f"{x:.6f}","20",f"{y:.6f}","30","0.0"]
    out += ["0","SEQEND"]
    return out

def _text(layer, x, y, height, text, rotation_deg=0.0, centered=False):
    safe = text.replace("\n", " ")
    out = [
        "0","TEXT","8",layer,
        "10",f"{x:.6f}","20",f"{y:.6f}","30","0.0",
        "40",f"{height:.6f}",
        "1",safe,
        "7","STANDARD",
        "50",f"{rotation_deg:.6f}"
    ]
    if centered:
        out += [
            "72","1",
            "73","2",
            "11",f"{x:.6f}","21",f"{y:.6f}","31","0.0",
        ]
    return out

def _text_pair(layer, x, y, height, bearing, distance, rotation_deg=0.0):
    # Separate TEXT entities survive more CAD import paths than stacked/centered text.
    gap = height * 1.25
    angle = math.radians(rotation_deg + 90.0)
    dx = (gap / 2.0) * math.cos(angle)
    dy = (gap / 2.0) * math.sin(angle)
    return (
        _text(layer, x + dx, y + dy, height, bearing, rotation_deg, centered=True)
        + _text(layer, x - dx, y - dy, height, distance, rotation_deg, centered=True)
    )

def _wrap360(a):
    return a % 360.0

def _az_to_math_rad(az_deg):
    return math.radians(90.0 - az_deg)

def _auto_text_height(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span <= 0:
        return 3.0
    return max(1.0, span * 0.02)

def _auto_label_offset(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span <= 0:
        return 8.0
    return max(5.0, span * 0.04)

def _deg_to_dms_text(deg):
    deg = abs(deg)
    d = int(deg)
    m_float = (deg - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{d:02d} {m:02d} {s:05.2f}"

def _bearing_from_points(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist <= 1e-9:
        return "N 00 00 00.00 E", 0.0, dist
    az = _wrap360(math.degrees(math.atan2(dx, dy)))
    if 0.0 <= az < 90.0:
        ns, ew, ang = "N", "E", az
    elif 90.0 <= az < 180.0:
        ns, ew, ang = "S", "E", 180.0 - az
    elif 180.0 <= az < 270.0:
        ns, ew, ang = "S", "W", az - 180.0
    else:
        ns, ew, ang = "N", "W", 360.0 - az
    return f"{ns} {_deg_to_dms_text(ang)} {ew}", az, dist

def _segment_midpoint(p1, p2):
    return ((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)

def _drawing_center(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

def _rotation_for_readable_text(az):
    rot = 90.0 - az
    while rot <= -180.0:
        rot += 360.0
    while rot > 180.0:
        rot -= 360.0
    if rot > 90.0:
        rot -= 180.0
    elif rot < -90.0:
        rot += 180.0
    return rot

def _offset_point(mid, az, offset):
    # offset perpendicular to segment
    t = _az_to_math_rad(_wrap360(az + 90.0))
    return (mid[0] + offset * math.cos(t), mid[1] + offset * math.sin(t))

def _outside_label_point(mid, az, offset, drawing_center):
    left = _offset_point(mid, az, offset)
    right = _offset_point(mid, az, -offset)
    left_dist = math.hypot(left[0] - drawing_center[0], left[1] - drawing_center[1])
    right_dist = math.hypot(right[0] - drawing_center[0], right[1] - drawing_center[1])
    return left if left_dist >= right_dist else right

def _tick_mark(center, az, size):
    t = _az_to_math_rad(_wrap360(az + 90.0))
    dx = (size / 2.0) * math.cos(t)
    dy = (size / 2.0) * math.sin(t)
    return (center[0] - dx, center[1] - dy), (center[0] + dx, center[1] + dy)

def export_dxf(path, points, segment_ranges, vertices):
    lines = []
    lines += _dxf_header()

    for seg in segment_ranges:
        s = seg["start_idx"]
        e = seg["end_idx"]
        p1 = points[s]
        p2 = points[e]
        if seg["type"] == "line":
            lines += _line("BOUNDARY", p1[0], p1[1], p2[0], p2[1])
        else:
            pts = points[s:e+1]
            lines += _polyline("CURVE", pts)

    txt_h = _auto_text_height(points)
    off = _auto_label_offset(points)
    center = _drawing_center(points)

    # Bearing and distance labels for every line segment.
    # Labels are offset outside the traverse so vertical/selected calls do not hide the text.
    for seg in segment_ranges:
        if seg["type"] != "line":
            continue
        s = seg["start_idx"]
        e = seg["end_idx"]
        p1 = points[s]
        p2 = points[e]
        bearing, az, dist = _bearing_from_points(p1, p2)
        distance = f"{dist:.2f}'"
        mid = _segment_midpoint(p1, p2)
        rot = _rotation_for_readable_text(az)

        lx, ly = _outside_label_point(mid, az, off * 0.85, center)
        if dist < (txt_h * 10.0):
            short_lx, short_ly = _outside_label_point(mid, az, off * 1.45, center)
            lx, ly = short_lx, short_ly
        t1, t2 = _tick_mark(mid, az, txt_h * 1.5)
        lines += _line("BD_TICKS", t1[0], t1[1], t2[0], t2[1])

        lines += _text_pair("BEARING_DISTANCE", lx, ly, txt_h, bearing, distance, rot)

    for v in vertices:
        cx, cy = v["E"], v["N"]
        az_in = v["az_in"]
        clockwise = v["side"] == "R"
        mid_az = _wrap360(az_in + (v["defl_abs"] / 2.0 if clockwise else -v["defl_abs"] / 2.0))
        tmid = _az_to_math_rad(mid_az)
        lx = cx + off * math.cos(tmid)
        ly = cy + off * math.sin(tmid)

        defl = _deg_to_dms_text(v["defl_abs"])
        interior = _deg_to_dms_text(v["interior"])
        label = f"{v['side']} {defl}  Int {interior}"
        lines += _text("ANGLE", lx, ly, txt_h, label)

    lines += _dxf_footer()

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

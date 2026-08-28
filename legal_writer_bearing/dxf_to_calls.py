import math
from dataclasses import dataclass
from typing import List, Tuple

EPS = 1e-12

@dataclass
class SegmentCall:
    kind: str  # LINE or CURVE

    bearing: str = ""
    distance_ft: float = 0.0

    curve_dir: str = ""      # LEFT or RIGHT
    radius_ft: float = 0.0
    delta_dms: str = ""
    arc_length_ft: float = 0.0
    chord_bearing: str = ""
    chord_distance_ft: float = 0.0

    start: Tuple[float, float] = (0.0, 0.0)
    end: Tuple[float, float] = (0.0, 0.0)

def _deg_to_dms_parts(deg: float):
    deg = abs(deg)
    d = int(deg)
    m_float = (deg - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    s_rounded = int(round(s))
    if s_rounded == 60:
        s_rounded = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return d, m, s_rounded

def _format_dms_2digit(deg: float) -> str:
    d, m, s = _deg_to_dms_parts(deg)
    if d < 100:
        dd = f"{d:02d}"
    else:
        dd = str(d)
    return f"{dd} degrees {m:02d} minutes {s:02d} seconds"

def bearing_quadrant(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[str, float]:
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1

    az = math.degrees(math.atan2(dx, dy))  # atan2(E, N)
    if az < 0:
        az += 360.0

    if 0 <= az < 90:
        quad = ("North", "East")
        ang = az
    elif 90 <= az < 180:
        quad = ("South", "East")
        ang = 180 - az
    elif 180 <= az < 270:
        quad = ("South", "West")
        ang = az - 180
    else:
        quad = ("North", "West")
        ang = 360 - az

    return f"{quad[0]} {_format_dms_2digit(ang)} {quad[1]}", az

def dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def bulge_to_arc(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float):
    c = dist(p1, p2)
    if abs(bulge) < EPS or c < EPS:
        return 0.0, 0.0, 0.0, c, bearing_quadrant(p1, p2)[0]

    delta = 4.0 * math.atan(abs(bulge))  # radians
    r = (c * (1.0 + bulge * bulge)) / (4.0 * abs(bulge))
    arc_len = r * delta
    chord_brg = bearing_quadrant(p1, p2)[0]
    return r, delta, arc_len, c, chord_brg

def delta_to_dms(delta_rad: float) -> str:
    return _format_dms_2digit(math.degrees(delta_rad))

def reorder_closed_polyline(vertices: List[Tuple[float, float]], bulges: List[float], start_index: int, direction: str):
    n = len(vertices)
    if n < 3:
        raise ValueError("Polyline must have at least 3 vertices.")

    if abs(vertices[0][0]-vertices[-1][0]) < 1e-9 and abs(vertices[0][1]-vertices[-1][1]) < 1e-9:
        vertices = vertices[:-1]
        bulges = bulges[:-1]
        n = len(vertices)

    idx = [(start_index + k) % n for k in range(n)]

    area2 = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area2 += (x1 * y2 - x2 * y1)
    original_is_ccw = area2 > 0

    want_ccw = (direction.upper() == "CCW")

    if want_ccw == original_is_ccw:
        ordered_vertices = [vertices[i] for i in idx]
        ordered_bulges = [bulges[i] for i in idx]
        return ordered_vertices, ordered_bulges

    idx_rev = [(start_index - k) % n for k in range(n)]
    ordered_vertices = [vertices[i] for i in idx_rev]

    ordered_bulges = []
    for k in range(n):
        prev = idx_rev[(k + 1) % n]
        ordered_bulges.append(-bulges[prev])
    return ordered_vertices, ordered_bulges

def calls_from_vertices(vertices: List[Tuple[float, float]], bulges: List[float]):
    n = len(vertices)
    calls = []
    for i in range(n):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % n]
        b = bulges[i]
        if abs(b) < EPS:
            brg, _az = bearing_quadrant(p1, p2)
            calls.append(SegmentCall(kind="LINE", bearing=brg, distance_ft=dist(p1, p2), start=p1, end=p2))
        else:
            r, delta_rad, arc_len, chord_len, chord_brg = bulge_to_arc(p1, p2, b)
            curve_dir = "LEFT" if b > 0 else "RIGHT"
            calls.append(SegmentCall(kind="CURVE", curve_dir=curve_dir, radius_ft=r, delta_dms=delta_to_dms(delta_rad),
                                     arc_length_ft=arc_len, chord_bearing=chord_brg, chord_distance_ft=chord_len,
                                     start=p1, end=p2))
    return calls

def format_calls_schoel_lines(calls, decimals: int = 2, close_with_pob: bool = True):
    lines = []
    for c in calls:
        if c.kind == "LINE":
            d = round(c.distance_ft, decimals)
            lines.append(f"thence run {c.bearing} {d:.{decimals}f} feet;")
        else:
            arc = round(c.arc_length_ft, decimals)
            r = round(c.radius_ft, decimals)
            cd = round(c.chord_distance_ft, decimals)
            dir_word = "left" if c.curve_dir.upper() == "LEFT" else "right"
            lines.append(
                f"thence run {arc:.{decimals}f} feet along a curve to the {dir_word} having a radius of {r:.{decimals}f} feet, "
                f"a delta angle of {c.delta_dms}, and a chord bearing and distance of {c.chord_bearing} {cd:.{decimals}f} feet;"
            )

    if close_with_pob and lines:
        last = lines[-1]
        if last.endswith(";"):
            lines[-1] = last[:-1] + " back to the Point of Beginning."
        else:
            lines[-1] = last + " back to the Point of Beginning."
    return lines

def signed_area_chords(vertices: List[Tuple[float, float]]) -> float:
    area2 = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    return 0.5 * area2

def signed_area_with_bulges(vertices: List[Tuple[float, float]], bulges: List[float]) -> float:
    a = signed_area_chords(vertices)
    n = len(vertices)
    for i in range(n):
        b = bulges[i]
        if abs(b) < EPS:
            continue
        p1 = vertices[i]
        p2 = vertices[(i + 1) % n]
        c = dist(p1, p2)
        if c < EPS:
            continue
        theta = 4.0 * math.atan(abs(b))
        r = (c * (1.0 + b * b)) / (4.0 * abs(b))
        seg_area = 0.5 * r * r * (theta - math.sin(theta))
        a += seg_area if b > 0 else -seg_area
    return a

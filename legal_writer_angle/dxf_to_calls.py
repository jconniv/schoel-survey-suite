import math
from dataclasses import dataclass, field
from typing import List, Tuple

EPS = 1e-12
ZERO_SEG_TOL = 1e-8
DIR_WORDS = [
    "Northerly",
    "Northeasterly",
    "Easterly",
    "Southeasterly",
    "Southerly",
    "Southwesterly",
    "Westerly",
    "Northwesterly",
]
BOUNDARIES = [14.036243467926479, 75.96375653207352, 104.03624346792648, 165.96375653207352, 194.03624346792648, 255.96375653207352, 284.03624346792645, 345.96375653207355]


@dataclass
class SegmentCall:
    kind: str  # LINE or CURVE
    start: Tuple[float, float] = (0.0, 0.0)
    end: Tuple[float, float] = (0.0, 0.0)

    # LINE fields
    line_azimuth: float = 0.0
    direction_word: str = ""
    distance_ft: float = 0.0

    # CURVE fields
    curve_dir: str = ""  # LEFT or RIGHT
    radius_ft: float = 0.0
    delta_deg: float = 0.0
    delta_dms: str = ""
    arc_length_ft: float = 0.0
    chord_azimuth: float = 0.0
    chord_distance_ft: float = 0.0
    chord_bearing: str = ""
    start_tangent_azimuth: float = 0.0
    end_tangent_azimuth: float = 0.0
    direction_words: List[str] = field(default_factory=list)


def normalize_azimuth(az: float) -> float:
    az %= 360.0
    if az < 0:
        az += 360.0
    return az


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


def format_dms(deg: float) -> str:
    d, m, s = _deg_to_dms_parts(deg)
    return f"{d:02d}°{m:02d}'{s:02d}\""


def bearing_quadrant(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[str, float]:
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1

    az = math.degrees(math.atan2(dx, dy))  # atan2(E, N)
    az = normalize_azimuth(az)

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

    return f"{quad[0]} {format_dms(ang)} {quad[1]}", az


def direction_word_from_azimuth(az: float) -> str:
    az = normalize_azimuth(az)
    if az < BOUNDARIES[0] or az >= BOUNDARIES[-1]:
        return DIR_WORDS[0]
    for idx, boundary in enumerate(BOUNDARIES[:-1], start=1):
        if az < boundary:
            return DIR_WORDS[idx - 1]
        next_boundary = BOUNDARIES[idx]
        if boundary <= az < next_boundary:
            return DIR_WORDS[idx]
    return DIR_WORDS[0]


def _article_for(word: str) -> str:
    return "an" if word and word[0].lower() in "aeiou" else "a"


def direction_phrase(words: List[str]) -> str:
    if not words:
        return ""
    if len(words) == 1:
        word = words[0]
        return f"in {_article_for(word)} {word} direction"
    if len(words) == 2:
        joined = f"{words[0]} and {words[1]}"
    else:
        joined = ", ".join(words[:-1]) + f" and {words[-1]}"
    return f"in a {joined} direction"


def dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def bulge_to_arc(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float):
    c = dist(p1, p2)
    if abs(bulge) < EPS or c < EPS:
        return 0.0, 0.0, 0.0, c, bearing_quadrant(p1, p2)[0], bearing_quadrant(p1, p2)[1]

    delta = 4.0 * math.atan(abs(bulge))  # radians
    r = (c * (1.0 + bulge * bulge)) / (4.0 * abs(bulge))
    arc_len = r * delta
    chord_brg, chord_az = bearing_quadrant(p1, p2)
    return r, delta, arc_len, c, chord_brg, chord_az


def signed_area_chords(vertices: List[Tuple[float, float]]) -> float:
    area2 = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    return 0.5 * area2


def signed_area_with_bulges(vertices: List[Tuple[float, float]], bulges: List[float]) -> float:
    area = signed_area_chords(vertices)
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
        area += seg_area if b > 0 else -seg_area
    return area


def reorder_closed_polyline(vertices: List[Tuple[float, float]], bulges: List[float], start_index: int, direction: str):
    """
    Reorder a closed DXF polyline from the selected POB.

    This matches the Bearing Legal Writer logic. The selected radio button
    chooses the actual polygon winding, not just the label text:

        CCW = counterclockwise polygon order
        CW  = clockwise polygon order

    This is the key fix for the Birmingham Interior Angle writer.
    """
    n = len(vertices)
    if n < 3:
        raise ValueError("Polyline must have at least 3 vertices.")

    if abs(vertices[0][0] - vertices[-1][0]) < 1e-9 and abs(vertices[0][1] - vertices[-1][1]) < 1e-9:
        vertices = vertices[:-1]
        bulges = bulges[:-1]
        n = len(vertices)

    start_index = int(start_index or 0) % n
    idx = [(start_index + k) % n for k in range(n)]

    area2 = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area2 += (x1 * y2 - x2 * y1)
    original_is_ccw = area2 > 0

    requested = (direction or "CCW").strip().upper()
    want_ccw = requested not in ("CW", "CLOCKWISE")

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

def _curve_center_and_angles(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float):
    c = dist(p1, p2)
    if c < EPS or abs(bulge) < EPS:
        return None

    delta = 4.0 * math.atan(abs(bulge))
    radius = (c * (1.0 + bulge * bulge)) / (4.0 * abs(bulge))
    mx = (p1[0] + p2[0]) / 2.0
    my = (p1[1] + p2[1]) / 2.0
    h = math.sqrt(max(radius * radius - (c / 2.0) ** 2, 0.0))
    ux = (p2[0] - p1[0]) / c
    uy = (p2[1] - p1[1]) / c
    left_px = -uy
    left_py = ux

    if bulge > 0:
        cx = mx + left_px * h
        cy = my + left_py * h
        ccw = True
    else:
        cx = mx - left_px * h
        cy = my - left_py * h
        ccw = False

    start_ang = math.atan2(p1[1] - cy, p1[0] - cx)
    end_ang = math.atan2(p2[1] - cy, p2[0] - cx)
    return cx, cy, radius, start_ang, end_ang, ccw


def _arc_point(cx: float, cy: float, radius: float, angle_rad: float) -> Tuple[float, float]:
    return (cx + radius * math.cos(angle_rad), cy + radius * math.sin(angle_rad))


def _compress_direction_words(words: List[str]) -> List[str]:
    compressed: List[str] = []
    for word in words:
        if not compressed or compressed[-1] != word:
            compressed.append(word)
    if len(compressed) <= 3:
        return compressed
    mid = compressed[len(compressed) // 2]
    result = [compressed[0]]
    if mid not in (result[-1], compressed[-1]):
        result.append(mid)
    if compressed[-1] != result[-1]:
        result.append(compressed[-1])
    return result


def _curve_direction_words(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float, chord_azimuth: float, delta_deg: float) -> List[str]:
    """Return Birmingham-style travel direction words for the arc."""
    if delta_deg < 40.0:
        return [direction_word_from_azimuth(chord_azimuth)]

    arc_data = _curve_center_and_angles(p1, p2, bulge)
    if arc_data is None:
        return [direction_word_from_azimuth(chord_azimuth)]

    cx, cy, radius, start_ang, end_ang, ccw = arc_data
    if ccw:
        total = (end_ang - start_ang) % (2.0 * math.pi)
    else:
        total = (start_ang - end_ang) % (2.0 * math.pi)

    steps = max(12, int(math.ceil(delta_deg / 5.0)))
    pts = []
    for i in range(steps + 1):
        frac = i / steps
        if ccw:
            ang = start_ang + total * frac
        else:
            ang = start_ang - total * frac
        pts.append(_arc_point(cx, cy, radius, ang))

    words: List[str] = []
    for i in range(len(pts) - 1):
        _, seg_az = bearing_quadrant(pts[i], pts[i + 1])
        word = direction_word_from_azimuth(seg_az)
        if not words or words[-1] != word:
            words.append(word)

    return _compress_direction_words(words) or [direction_word_from_azimuth(chord_azimuth)]


def _turn_from_to(from_azimuth: float, to_azimuth: float, preferred: str | None = None) -> Tuple[str, float]:
    cw = (to_azimuth - from_azimuth) % 360.0
    ccw = (from_azimuth - to_azimuth) % 360.0
    pref = (preferred or "").upper()
    if pref == "CW":
        return "RIGHT", cw
    if pref == "CCW":
        return "LEFT", ccw
    if cw <= ccw:
        return "RIGHT", cw
    return "LEFT", ccw


def _is_tangent(a: float, b: float, tol_seconds: float = 10.0) -> bool:
    diff = min((a - b) % 360.0, (b - a) % 360.0)
    return diff * 3600.0 <= tol_seconds


def calls_from_vertices(vertices: List[Tuple[float, float]], bulges: List[float]) -> List[SegmentCall]:
    n = len(vertices)
    calls: List[SegmentCall] = []
    for i in range(n):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % n]
        b = bulges[i]
        seg_len = dist(p1, p2)
        if seg_len <= ZERO_SEG_TOL and abs(b) < EPS:
            continue
        if abs(b) < EPS:
            _, az = bearing_quadrant(p1, p2)
            calls.append(
                SegmentCall(
                    kind="LINE",
                    start=p1,
                    end=p2,
                    line_azimuth=az,
                    direction_word=direction_word_from_azimuth(az),
                    distance_ft=seg_len,
                )
            )
        else:
            radius, delta_rad, arc_len, chord_len, chord_bearing, chord_az = bulge_to_arc(p1, p2, b)
            delta_deg = math.degrees(delta_rad)
            if b > 0:
                curve_dir = "LEFT"
                start_tan = normalize_azimuth(chord_az + delta_deg / 2.0)
                end_tan = normalize_azimuth(chord_az - delta_deg / 2.0)
            else:
                curve_dir = "RIGHT"
                start_tan = normalize_azimuth(chord_az - delta_deg / 2.0)
                end_tan = normalize_azimuth(chord_az + delta_deg / 2.0)
            calls.append(
                SegmentCall(
                    kind="CURVE",
                    start=p1,
                    end=p2,
                    curve_dir=curve_dir,
                    radius_ft=radius,
                    delta_deg=delta_deg,
                    delta_dms=format_dms(delta_deg),
                    arc_length_ft=arc_len,
                    chord_azimuth=chord_az,
                    chord_distance_ft=chord_len,
                    chord_bearing=chord_bearing,
                    start_tangent_azimuth=start_tan,
                    end_tangent_azimuth=end_tan,
                    direction_words=_curve_direction_words(p1, p2, b, chord_az, delta_deg),
                )
            )
    return calls


def _curve_descriptor(call: SegmentCall, decimals: int) -> str:
    return (
        f"a curve to the {call.curve_dir.lower()} having a radius of {call.radius_ft:.{decimals}f} feet "
        f"and a central angle of {call.delta_dms}"
    )


def _curve_intro_from_previous(prev_call: SegmentCall | None, call: SegmentCall, tiny: float, preferred_turn: str | None = None) -> str:
    if prev_call is None:
        return f"thence along the arc of {_curve_descriptor(call, 2)}"

    if prev_call.kind == "LINE":
        prev_tangent = prev_call.line_azimuth
        relation = "angle measured to tangent"
    else:
        prev_tangent = prev_call.end_tangent_azimuth
        relation = "angle measured tangent to tangent"

    side, angle = _turn_from_to(prev_tangent, call.start_tangent_azimuth)
    if angle < tiny:
        return "thence along the arc of said curve"
    return f"thence {format_dms(angle)} to the {side.lower()} ({relation}) along the arc of said curve"


def _line_intro_from_previous(prev_call: SegmentCall | None, call: SegmentCall, tiny: float, preferred_turn: str | None = None) -> str:
    direction = direction_phrase([call.direction_word])
    if prev_call is None:
        return f"thence {direction}"
    if prev_call.kind == "CURVE":
        side, angle = _turn_from_to(prev_call.end_tangent_azimuth, call.line_azimuth)
        if angle < tiny:
            return f"thence tangent to said curve {direction}"
        return f"thence {format_dms(angle)} to the {side.lower()} (angle measured to tangent) {direction}"
    side, angle = _turn_from_to(prev_call.line_azimuth, call.line_azimuth)
    if angle < tiny:
        return f"thence continue along the previous course {direction}"
    return f"thence {format_dms(angle)} to the {side.lower()} {direction}"


def _ending_phrase(current: SegmentCall, next_call: SegmentCall | None, decimals: int, close_with_pob: bool, is_last: bool) -> str:
    if is_last:
        return " to the Point of Beginning." if close_with_pob else "."
    if next_call is None:
        return ";"

    if next_call.kind == "CURVE":
        if current.kind == "LINE":
            if _is_tangent(current.line_azimuth, next_call.start_tangent_azimuth):
                return f" to a point being the P.C. (point of curve) of {_curve_descriptor(next_call, decimals)};"
            return f" to a point lying on {_curve_descriptor(next_call, decimals)};"

        if _is_tangent(current.end_tangent_azimuth, next_call.start_tangent_azimuth):
            if current.curve_dir == next_call.curve_dir:
                label = "P.C.C. (point of compound curve)"
            else:
                label = "P.R.C. (point of reverse curve)"
            return f" to a point being the {label} of {_curve_descriptor(next_call, decimals)};"
        return f" to a point lying on {_curve_descriptor(next_call, decimals)};"

    if current.kind == "CURVE" and next_call.kind == "LINE" and _is_tangent(current.end_tangent_azimuth, next_call.line_azimuth):
        return " to a point being the P.T. (point of tangent) of said curve;"

    return ";"


def format_calls_birmingham_lines(calls: List[SegmentCall], decimals: int = 2, close_with_pob: bool = True, preferred_turn: str | None = None) -> List[str]:
    lines: List[str] = []
    tiny = 1.0 / 3600.0

    for idx, call in enumerate(calls):
        prev_call = calls[idx - 1] if idx > 0 else None
        next_call = calls[idx + 1] if idx + 1 < len(calls) else None
        is_last = idx == len(calls) - 1

        if call.kind == "LINE":
            prefix = _line_intro_from_previous(prev_call, call, tiny, None)
            ending = _ending_phrase(call, next_call, decimals, close_with_pob, is_last)
            text = f"{prefix} a distance of {call.distance_ft:.{decimals}f} feet{ending}"
            lines.append(text)
            continue

        prefix = _curve_intro_from_previous(prev_call, call, tiny, None)
        direction = direction_phrase(call.direction_words)
        ending = _ending_phrase(call, next_call, decimals, close_with_pob, is_last)
        text = (
            f"{prefix} {direction} a distance of {call.arc_length_ft:.{decimals}f} feet{ending}"
        )
        lines.append(text)

    return lines

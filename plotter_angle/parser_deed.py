import re

def _normalize(text: str) -> str:
    t = text.replace("º", "°")
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def dms_to_deg(d: int, m: int, s: float) -> float:
    return float(d) + float(m) / 60.0 + float(s) / 3600.0

def parse_dms(s: str) -> float:
    s = _normalize(s)
    m = re.search(r"(\d+)\s*°\s*(\d+)\s*'\s*(\d+(?:\.\d+)?)\s*\"", s)
    if m:
        return dms_to_deg(int(m.group(1)), int(m.group(2)), float(m.group(3)))
    m = re.search(r"(\d+)\s*°\s*(\d+)\s*'\s*(\d+(?:\.\d+)?)", s)
    if m:
        return dms_to_deg(int(m.group(1)), int(m.group(2)), float(m.group(3)))
    m = re.search(r"(\d+)\s*°\s*(\d+)\s*'", s)
    if m:
        return dms_to_deg(int(m.group(1)), int(m.group(2)), 0.0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*°", s)
    if m:
        return float(m.group(1))
    raise ValueError(f"Could not parse DMS angle from: {s}")

def parse_start_bearing(s: str) -> float:
    s = _normalize(s).upper()
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s) % 360.0

    m = re.search(r"\b([NS])\s*(.+?)\s*([EW])\b", s)
    if not m:
        if s in ["W","WEST","WESTERLY","WESTERLY DIRECTION"]:
            return 270.0
        if s in ["E","EAST","EASTERLY","EASTERLY DIRECTION"]:
            return 90.0
        if s in ["N","NORTH","NORTHERLY","NORTHERLY DIRECTION"]:
            return 0.0
        if s in ["S","SOUTH","SOUTHERLY","SOUTHERLY DIRECTION"]:
            return 180.0
        raise ValueError("Starting bearing not recognized. Use 270 or N 12°34'56\" E.")

    ns = m.group(1)
    ew = m.group(3)
    ang = parse_dms(m.group(2))

    if ns == "N" and ew == "E":
        az = ang
    elif ns == "S" and ew == "E":
        az = 180.0 - ang
    elif ns == "S" and ew == "W":
        az = 180.0 + ang
    else:
        az = 360.0 - ang
    return az % 360.0

_DMS_RE = r'(?P<ang>\d+\s*°\s*\d+\s*\'\s*\d+(?:\.\d+)?\s*\"|\d+\s*°\s*\d+\s*\'|\d+(?:\.\d+)?\s*°)'
_TURN_RE = re.compile(_DMS_RE + r"\s*(?:,|\s)*(?:TO\s+THE\s+)?(?P<side>RIGHT|LEFT)\b", re.IGNORECASE)

_CURVE_RE = re.compile(
    r"\bCURVE\b\s*(?:,|\s)*(?:TO\s+THE\s+)?(?P<dir>RIGHT|LEFT)\b"
    r".*?\bRADIUS\b\s*(?:OF\s*)?(?P<rad>[0-9]+(?:\.[0-9]+)?)"
    r".*?\b(?:CENTRAL\s+ANGLE|DELTA)\b\s*(?:OF|=)?\s*(?P<dms>" + _DMS_RE + r")",
    re.IGNORECASE
)

_ARC_RE = re.compile(
    r"\bALONG\b\s+THE\s+\bARC\b.*?\b(?:DISTANCE\s+OF|A\s+DISTANCE\s+OF)\s*(?P<dist>[0-9]+(?:\.[0-9]+)?)\s*FEET\b",
    re.IGNORECASE
)

_DIST_RE = re.compile(
    r"\b(?:DISTANCE\s+OF|A\s+DISTANCE\s+OF)\s*(?P<dist>[0-9]+(?:\.[0-9]+)?)\s*FEET\b",
    re.IGNORECASE
)

def _is_along_curve_prefix(clause_up: str, curve_start: int) -> bool:
    pre = clause_up[max(0, curve_start - 30):curve_start]
    return "ALONG" in pre

def parse_deed_to_steps(deed_text: str):
    t = _normalize(deed_text)
    parts = re.split(r"\bTHENCE\b|;", t, flags=re.IGNORECASE)
    parts = [p.strip(" ,.") for p in parts if p and p.strip()]

    steps = []
    log_lines = []

    pending_curve = None
    last_curve_step_index = None

    for idx, clause in enumerate(parts, start=1):
        p = clause.strip()
        if not p:
            continue
        p_up = p.upper()

        pos = 0
        arc_guard_end = -1

        while pos < len(p):
            m_turn = _TURN_RE.search(p, pos)
            m_arc = _ARC_RE.search(p, pos)
            m_curve = _CURVE_RE.search(p, pos)
            m_dist = _DIST_RE.search(p, pos)

            candidates = []
            for tag, m in [("turn", m_turn), ("arc", m_arc), ("curve", m_curve), ("dist", m_dist)]:
                if m:
                    candidates.append((m.start(), tag, m))
            if not candidates:
                break

            candidates.sort(key=lambda x: x[0])
            start, tag, m = candidates[0]

            if tag == "dist" and start < arc_guard_end:
                pos = m.end()
                continue

            if tag == "turn":
                side = "R" if m.group("side").upper() == "RIGHT" else "L"
                angle_deg = parse_dms(m.group("ang"))
                note = "angle measured to tangent" if "TANGENT" in p_up else ""
                steps.append({"type": "turn", "side": side, "angle_deg": angle_deg, "note": note})
                log_lines.append(f"{idx}. Turn {side}, angle {angle_deg:.8f} {note}".strip())
                pos = m.end()
                continue

            if tag == "arc":
                arc_dist = float(m.group("dist"))
                if pending_curve is not None:
                    steps.append({
                        "type": "curve",
                        "dir": pending_curve["dir"],
                        "radius": pending_curve["radius"],
                        "delta_deg": pending_curve["delta_deg"],
                        "arc": arc_dist
                    })
                    last_curve_step_index = len(steps) - 1
                    log_lines.append(f"{idx}. Curve {pending_curve['dir']}, R {pending_curve['radius']}, delta {pending_curve['delta_deg']:.8f}, arc {arc_dist}")
                    pending_curve = None
                else:
                    if last_curve_step_index is not None and steps[last_curve_step_index].get("arc") is None:
                        steps[last_curve_step_index]["arc"] = arc_dist
                        log_lines.append(f"{idx}. Arc distance applied to previous curve {arc_dist}")
                    else:
                        log_lines.append(f"{idx}. Arc distance found but no curve parameters were pending {arc_dist}")

                arc_guard_end = max(arc_guard_end, m.end())
                pos = m.end()
                continue

            if tag == "curve":
                dir_ = "R" if m.group("dir").upper() == "RIGHT" else "L"
                radius = float(m.group("rad"))
                delta_deg = parse_dms(m.group("dms"))
                if _is_along_curve_prefix(p_up, m.start()):
                    steps.append({"type": "curve", "dir": dir_, "radius": radius, "delta_deg": delta_deg, "arc": None})
                    last_curve_step_index = len(steps) - 1
                    log_lines.append(f"{idx}. Curve {dir_}, R {radius}, delta {delta_deg:.8f}, arc pending")
                    pending_curve = None
                else:
                    pending_curve = {"dir": dir_, "radius": radius, "delta_deg": delta_deg}
                    log_lines.append(f"{idx}. Curve parameters saved {dir_}, R {radius}, delta {delta_deg:.8f}")
                pos = m.end()
                continue

            if tag == "dist":
                pre = p_up[max(0, m.start() - 40):m.start()]
                if "ARC" in pre:
                    pos = m.end()
                    continue
                dist = float(m.group("dist"))
                steps.append({"type": "line", "dist": dist})
                log_lines.append(f"{idx}. Line dist {dist}")
                pos = m.end()
                continue

    if not steps:
        raise ValueError("No steps were parsed.")
    log = "Parse log\n" + "\n".join(log_lines)
    return steps, log

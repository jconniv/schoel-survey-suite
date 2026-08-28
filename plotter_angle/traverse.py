import math

def wrap360(a: float) -> float:
    return a % 360.0

def line_delta(dist: float, az_deg: float):
    az = math.radians(az_deg)
    dE = dist * math.sin(az)
    dN = dist * math.cos(az)
    return dE, dN

def curve_points(start_E, start_N, az_tan_deg, radius, delta_deg, dir_, n=90):
    sign = 1.0 if str(dir_).upper().startswith("R") else -1.0

    center_az = wrap360(az_tan_deg + 90.0 * sign)
    c_az_rad = math.radians(center_az)
    cx = start_E + radius * math.sin(c_az_rad)
    cy = start_N + radius * math.cos(c_az_rad)

    start_rad_az = wrap360(center_az + 180.0)

    pts = []
    for k in range(n):
        frac = k / (n - 1)
        rad_az = wrap360(start_rad_az + sign * delta_deg * frac)
        rad = math.radians(rad_az)
        x = cx + radius * math.sin(rad)
        y = cy + radius * math.cos(rad)
        pts.append((x, y))

    az_out = wrap360(az_tan_deg + sign * delta_deg)
    return pts, az_out

def solve_traverse(start_az_deg: float, steps: list):
    az = wrap360(start_az_deg)
    E, N = 0.0, 0.0

    points = [(E, N)]
    vertices = []
    segment_ranges = []

    for s in steps:
        t = s["type"].lower()

        if t == "turn":
            az_in = az
            side = s["side"].upper()
            ang = float(s["angle_deg"])
            sign = 1.0 if side.startswith("R") else -1.0
            az = wrap360(az + sign * ang)

            vertices.append({
                "point_index": len(points) - 1,
                "E": E,
                "N": N,
                "az_in": az_in,
                "az_out": az,
                "defl_signed": sign * ang,
                "defl_abs": abs(ang),
                "side": "R" if sign > 0 else "L",
                "interior": 180.0 - abs(ang),
                "note": s.get("note", "")
            })

        elif t == "line":
            start_idx = len(points) - 1
            dist = float(s["dist"])
            dE, dN = line_delta(dist, az)
            E += dE
            N += dN
            points.append((E, N))
            end_idx = len(points) - 1
            segment_ranges.append({"type": "line", "start_idx": start_idx, "end_idx": end_idx, "dist": dist})

        elif t == "curve":
            start_idx = len(points) - 1
            dir_ = s["dir"]
            radius = float(s["radius"])
            delta_deg = float(s["delta_deg"])
            pts, az_out = curve_points(E, N, az, radius, delta_deg, dir_, n=90)
            for p in pts[1:]:
                points.append(p)
            E, N = points[-1]
            az = az_out
            end_idx = len(points) - 1
            segment_ranges.append({"type": "curve", "start_idx": start_idx, "end_idx": end_idx, "dir": dir_, "radius": radius, "delta_deg": delta_deg})

        else:
            raise ValueError(f"Unknown step type: {t}")

    end_E, end_N = points[-1]
    misclosure = math.hypot(end_E - points[0][0], end_N - points[0][1])

    total_len = 0.0
    for s in steps:
        if s["type"] == "line":
            total_len += float(s["dist"])
        elif s["type"] == "curve":
            arc = s.get("arc", None)
            if arc is not None:
                total_len += float(arc)
            else:
                total_len += float(s["radius"]) * math.radians(float(s["delta_deg"]))

    ratio = (total_len / misclosure) if misclosure > 0 else float("inf")

    summary = (
        "Closure summary\n"
        f"End point Easting  {end_E:.4f}\n"
        f"End point Northing {end_N:.4f}\n"
        f"Linear misclosure  {misclosure:.4f}\n"
        f"Total length       {total_len:.4f}\n"
        f"Relative precision 1:{ratio:,.0f}\n"
        f"End azimuth        {az:.6f}\n"
    )

    return {"points": points, "vertices": vertices, "segment_ranges": segment_ranges, "summary": summary}

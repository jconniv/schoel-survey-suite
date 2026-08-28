import math
import re

USFT_PER_M = 3937.0 / 1200.0


bearing_re = re.compile(r'''^\s*([NS])\s*(\d{1,3})(?:[^\d]+(\d{1,2}))?(?:[^\d]+(\d{1,2}(?:\.\d+)?))?\s*([EW])\s*$''', re.I)
compact_bearing_re = re.compile(r'^\s*([NS])\s*(\d{2,7})\s*([EW])\s*$', re.I)

def dms_to_decimal(d=0, m=0, s=0.0):
    return float(d) + float(m)/60.0 + float(s)/3600.0


def decimal_to_dms(value: float):
    value = abs(float(value))
    d = int(value)
    m_float = (value - d) * 60
    m = int(m_float)
    s = round((m_float - m) * 60, 2)
    if s >= 60:
        s -= 60
        m += 1
    if m >= 60:
        m -= 60
        d += 1
    return d, m, s


def parse_bearing(text: str) -> float:
    raw = text.strip().upper()
    txt = raw.replace('°', ' ').replace("'", ' ').replace('"', ' ')
    txt = re.sub(r'\s+', ' ', txt)
    m = bearing_re.match(txt)
    if not m:
        compact = compact_bearing_re.match(raw.replace(' ', ''))
        if compact:
            ns, digits, ew = compact.groups()
            if len(digits) <= 3:
                d, mm, ss = digits, 0, 0
            elif len(digits) in (4, 5):
                d, mm, ss = digits[:-2], digits[-2:], 0
            else:
                d, mm, ss = digits[:-4], digits[-4:-2], digits[-2:]
            m = (ns, d, mm, ss, ew)
        else:
            raise ValueError(f'Could not parse bearing: {text}')
    else:
        m = m.groups()
    ns, d, mm, ss, ew = m
    angle = dms_to_decimal(d, mm or 0, ss or 0)
    if ns == 'N' and ew == 'E':
        az = angle
    elif ns == 'S' and ew == 'E':
        az = 180 - angle
    elif ns == 'S' and ew == 'W':
        az = 180 + angle
    else:
        az = 360 - angle
    return az % 360


def azimuth_to_bearing(azimuth: float) -> str:
    az = azimuth % 360.0
    if az <= 90:
        ns, ew, ang = 'N', 'E', az
    elif az <= 180:
        ns, ew, ang = 'S', 'E', 180 - az
    elif az <= 270:
        ns, ew, ang = 'S', 'W', az - 180
    else:
        ns, ew, ang = 'N', 'W', 360 - az
    d, m, s = decimal_to_dms(ang)
    return f'{ns}{d:02d}°{m:02d}\'{s:05.2f}"{ew}'


def azimuth_to_ne_delta(azimuth: float, distance: float):
    rad = math.radians(azimuth)
    dN = math.cos(rad) * distance
    dE = math.sin(rad) * distance
    return dN, dE


def closure_from_calls(calls):
    northing = 0.0
    easting = 0.0
    rows = []
    for idx, (bearing, distance) in enumerate(calls, start=1):
        az = parse_bearing(bearing)
        dN, dE = azimuth_to_ne_delta(az, float(distance))
        northing += dN
        easting += dE
        rows.append({
            'line': idx,
            'bearing': bearing,
            'distance': float(distance),
            'azimuth': az,
            'dN': dN,
            'dE': dE,
            'northing': northing,
            'easting': easting,
        })
    linear = math.hypot(northing, easting)
    perimeter = sum(float(d) for _, d in calls)
    precision = (perimeter / linear) if linear > 0 else float('inf')
    return {
        'northing_error': northing,
        'easting_error': easting,
        'linear_error': linear,
        'perimeter': perimeter,
        'precision': precision,
        'rows': rows,
    }


def parse_bearing_distance_lines(text: str):
    calls = []
    for raw in text.splitlines():
        line = raw.strip().rstrip(',;')
        if not line:
            continue
        m = re.search(r'([NS].*?[EW])[^\d\-\.]*([0-9]+(?:\.[0-9]+)?)', line, re.I)
        if not m:
            parts = re.split(r'\t|,', line)
            if len(parts) >= 2:
                calls.append((parts[0].strip(), float(parts[1].strip())))
                continue
            raise ValueError(f'Could not read bearing and distance from line: {raw}')
        calls.append((m.group(1).strip(), float(m.group(2))))
    return calls

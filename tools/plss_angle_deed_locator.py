import os
import re
import sys
import math
import tkinter as tk
import zipfile
from tkinter import ttk, filedialog, messagebox
from xml.etree import ElementTree as ET

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, copy_to_clipboard, COLORS

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PLOTTER_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'plotter_angle'))
if PLOTTER_DIR not in sys.path:
    sys.path.insert(0, PLOTTER_DIR)

from traverse import solve_traverse, wrap360, line_delta, curve_points  # type: ignore

SECTION_SIZE_FT = 5280.0

SECTION_PATTERNS = [
    re.compile(r'\bSECTION\s+(\d{1,2})\b', re.I),
    re.compile(r'\bSEC\.?\s*(\d{1,2})\b', re.I),
]
TOWNSHIP_PATTERNS = [
    re.compile(r'\bTOWNSHIP\s*(\d{1,3})\s*(NORTH|SOUTH|N|S)\b', re.I),
    re.compile(r'\bT\.?\s*-?\s*(\d{1,3})\s*-?\s*(NORTH|SOUTH|N|S)\b', re.I),
    re.compile(r'\bT\s*(\d{1,3})(N|S)\b', re.I),
]
RANGE_PATTERNS = [
    re.compile(r'\bRANGE\s*(\d{1,3})\s*(EAST|WEST|E|W)\b', re.I),
    re.compile(r'\bR\.?\s*-?\s*(\d{1,3})\s*-?\s*(EAST|WEST|E|W)\b', re.I),
    re.compile(r'\bR\s*(\d{1,3})(E|W)\b', re.I),
]
STATE_PATTERNS = [
    re.compile(r'\bALABAMA\b', re.I),
    re.compile(r'\bMISSISSIPPI\b', re.I),
    re.compile(r'\bFLORIDA\b', re.I),
    re.compile(r'\bGEORGIA\b', re.I),
]

CARDINAL_MAP = {
    'NORTHERLY': 0.0, 'NORTH': 0.0, 'N': 0.0,
    'NORTHEASTERLY': 45.0, 'NE': 45.0,
    'EASTERLY': 90.0, 'EAST': 90.0, 'E': 90.0,
    'SOUTHEASTERLY': 135.0, 'SE': 135.0,
    'SOUTHERLY': 180.0, 'SOUTH': 180.0, 'S': 180.0,
    'SOUTHWESTERLY': 225.0, 'SW': 225.0,
    'WESTERLY': 270.0, 'WEST': 270.0, 'W': 270.0,
    'NORTHWESTERLY': 315.0, 'NW': 315.0,
}

QUARTER_CORNERS = {
    'NORTH QUARTER CORNER': 'N',
    'SOUTH QUARTER CORNER': 'S',
    'EAST QUARTER CORNER': 'E',
    'WEST QUARTER CORNER': 'W',
    'N QUARTER CORNER': 'N',
    'S QUARTER CORNER': 'S',
    'E QUARTER CORNER': 'E',
    'W QUARTER CORNER': 'W',
}

DMS_RE = r'(\d+\s*[°º]\s*\d+\s*[\'’]\s*\d+(?:\.\d+)?\s*["”]?|\d+\s*[°º]\s*\d+\s*[\'’]|\d+(?:\.\d+)?\s*[°º])'
TURN_RE = re.compile(DMS_RE + r'\s*(?:,|\s)*(?:TO\s+THE\s+)?(RIGHT|LEFT)\b', re.I)
DIST_RE = re.compile(r'\b(?:A\s+DISTANCE\s+OF|DISTANCE\s+OF)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:FEET|FOOT|FT|\")?\b', re.I)
CURVE_RE = re.compile(
    r'\b(?:CURVE|ARC)\b.*?\bTO\s+THE\s+(RIGHT|LEFT)\b.*?\bRADIUS\b\s*(?:OF\s*)?([0-9]+(?:\.[0-9]+)?)'
    r'.*?\b(?:CENTRAL\s+ANGLE|DELTA)\b\s*(?:OF|=)?\s*' + DMS_RE,
    re.I,
)
ALONG_ARC_RE = re.compile(r'\bALONG\s+SAID\s+ARC\b|\bALONG\s+THE\s+ARC\b', re.I)
TANGENT_NOTE_RE = re.compile(r'ANGLE\s+MEASURED\s+TO\s+TANGENT|ANGLE\s+MEASURED\s+TANGENT\s+TO\s+TANGENT', re.I)


def dms_to_decimal(d=0, m=0, s=0.0):
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def parse_dms(s: str) -> float:
    s = s.replace('º', '°').replace('’', "'").replace('‘', "'").replace('”', '"').replace('“', '"')
    m = re.search(r'(\d+)\s*°\s*(\d+)\s*[\']\s*(\d+(?:\.\d+)?)\s*[\"]?', s)
    if m:
        return dms_to_decimal(int(m.group(1)), int(m.group(2)), float(m.group(3)))
    m = re.search(r'(\d+)\s*°\s*(\d+)\s*[\']', s)
    if m:
        return dms_to_decimal(int(m.group(1)), int(m.group(2)), 0.0)
    m = re.search(r'(\d+(?:\.\d+)?)\s*°', s)
    if m:
        return float(m.group(1))
    raise ValueError(f'Could not parse DMS from {s!r}')


def normalize_dir(word: str) -> str:
    w = word.upper().strip()
    return {'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W'}.get(w, w)


def normalize_text(text: str) -> str:
    t = text.upper()
    replacements = {
        '¼': ' 1/4 ', '½': ' 1/2 ', '¾': ' 3/4 ',
        'N.E.': ' NE ', 'N.W.': ' NW ', 'S.E.': ' SE ', 'S.W.': ' SW ',
        'N.E': ' NE ', 'N.W': ' NW ', 'S.E': ' SE ', 'S.W': ' SW ',
        'NORTHEAST QUARTER': ' NE 1/4 ', 'NORTHWEST QUARTER': ' NW 1/4 ',
        'SOUTHEAST QUARTER': ' SE 1/4 ', 'SOUTHWEST QUARTER': ' SW 1/4 ',
        'NORTHEAST ONE-QUARTER': ' NE 1/4 ', 'NORTHWEST ONE-QUARTER': ' NW 1/4 ',
        'SOUTHEAST ONE-QUARTER': ' SE 1/4 ', 'SOUTHWEST ONE-QUARTER': ' SW 1/4 ',
        'NORTH HALF': ' N 1/2 ', 'SOUTH HALF': ' S 1/2 ', 'EAST HALF': ' E 1/2 ', 'WEST HALF': ' W 1/2 ',
        'POINT OF BEGINNING': ' POB ', 'TRUE POINT OF BEGINNING': ' POB ',
        'COMMENCING AT': ' COMMENCE AT ',
        'RIGHT-OF-WAY': ' RIGHT OF WAY ',
        '¼-¼': ' 1/4-1/4 ',
        '¼-1/4': ' 1/4-1/4 ',
        '1/4-¼': ' 1/4-1/4 ',
        '1/4 SECTION': ' 1/4 SECTION ',
        'º': '°', '’': "'", '‘': "'", '“': '"', '”': '"',
    }
    for a, b in replacements.items():
        t = t.replace(a, b)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def find_state(text: str):
    for pat in STATE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).title()
    return None


def find_section_info(text: str):
    norm = normalize_text(text)
    sec = twp = rng = None
    for pat in SECTION_PATTERNS:
        m = pat.search(norm)
        if m:
            sec = int(m.group(1))
            break
    for pat in TOWNSHIP_PATTERNS:
        m = pat.search(norm)
        if m:
            twp = f"{int(m.group(1))} {normalize_dir(m.group(2))}"
            break
    for pat in RANGE_PATTERNS:
        m = pat.search(norm)
        if m:
            rng = f"{int(m.group(1))} {normalize_dir(m.group(2))}"
            break
    return sec, twp, rng


def rect_for_token_sequence(seq_outer_to_inner):
    rect = [0.0, 0.0, 1.0, 1.0]
    for token, frac in seq_outer_to_inner:
        x0, y0, x1, y1 = rect
        mx = (x0 + x1) / 2.0
        my = (y0 + y1) / 2.0
        token = token.upper()
        if frac == '1/4':
            if token == 'NW':
                rect = [x0, my, mx, y1]
            elif token == 'NE':
                rect = [mx, my, x1, y1]
            elif token == 'SW':
                rect = [x0, y0, mx, my]
            elif token == 'SE':
                rect = [mx, y0, x1, my]
        elif frac == '1/2':
            if token == 'N':
                rect = [x0, my, x1, y1]
            elif token == 'S':
                rect = [x0, y0, x1, my]
            elif token == 'E':
                rect = [mx, y0, x1, y1]
            elif token == 'W':
                rect = [x0, y0, mx, y1]
    return rect


def rect_to_feet(rect):
    return [rect[0] * SECTION_SIZE_FT, rect[1] * SECTION_SIZE_FT, rect[2] * SECTION_SIZE_FT, rect[3] * SECTION_SIZE_FT]


def point_for_corner(rect_ft, corner):
    x0, y0, x1, y1 = rect_ft
    mapping = {
        'NW': (x0, y1), 'NE': (x1, y1), 'SW': (x0, y0), 'SE': (x1, y0),
        'N': ((x0 + x1) / 2.0, y1), 'S': ((x0 + x1) / 2.0, y0),
        'E': (x1, (y0 + y1) / 2.0), 'W': (x0, (y0 + y1) / 2.0),
        'CENTER': ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
    }
    return mapping.get(corner, ((x0 + x1) / 2.0, (y0 + y1) / 2.0))


def parse_aliquot_chains(text: str):
    norm = normalize_text(text)
    token = r'(?:(?:NE|NW|SE|SW)\s*1/4|(?:N|S|E|W)\s*1/2)'
    pattern = re.compile(rf'({token}(?:\s+OF\s+(?:THE\s+)?{token})+|{token})', re.I)
    chains = []
    seen = set()
    for m in pattern.finditer(norm):
        cand = re.sub(r'\s+', ' ', m.group(1).strip())
        cand = re.sub(r'\bTHE\b\s*', '', cand).strip()
        if cand in seen:
            continue
        seen.add(cand)
        parts = re.split(r'\s+OF\s+', cand)
        seq_raw = []
        for part in parts:
            mm = re.match(r'(NE|NW|SE|SW|N|S|E|W)\s*(1/4|1/2)', part.strip(), re.I)
            if mm:
                seq_raw.append((mm.group(1).upper(), mm.group(2)))
        if seq_raw:
            seq_outer_to_inner = list(reversed(seq_raw))
            chains.append({'text': cand, 'seq': seq_outer_to_inner, 'rect': rect_for_token_sequence(seq_outer_to_inner)})
    return chains


def extract_beginning_reference(text: str, aliquot_chains):
    norm = normalize_text(text)
    m = re.search(r'\b(?:BEGIN AT|COMMENCE AT)\b(.+?)(?:;|, THENCE| THENCE )', norm)
    clause = m.group(1) if m else ''
    candidates = [ch for ch in aliquot_chains if ch['text'] in clause]
    ref_chain = sorted(candidates, key=lambda c: len(c['text']), reverse=True)[0] if candidates else (aliquot_chains[0] if aliquot_chains else None)
    corner = None
    for long_name, short in [('NORTHEAST', 'NE'), ('NORTHWEST', 'NW'), ('SOUTHEAST', 'SE'), ('SOUTHWEST', 'SW'), ('NE', 'NE'), ('NW', 'NW'), ('SE', 'SE'), ('SW', 'SW')]:
        if re.search(rf'\b{long_name}\s+CORNER\b', clause):
            corner = short
            break
    quarter_corner = None
    for phrase, side in QUARTER_CORNERS.items():
        if phrase in clause:
            quarter_corner = side
            break
    return {'clause': clause, 'ref_chain': ref_chain, 'ref_corner': corner, 'quarter_corner': quarter_corner}


def section_point_for_quarter_corner(side):
    side = side.upper()
    if side == 'N':
        return (SECTION_SIZE_FT / 2.0, SECTION_SIZE_FT)
    if side == 'S':
        return (SECTION_SIZE_FT / 2.0, 0.0)
    if side == 'E':
        return (SECTION_SIZE_FT, SECTION_SIZE_FT / 2.0)
    if side == 'W':
        return (0.0, SECTION_SIZE_FT / 2.0)
    return (SECTION_SIZE_FT / 2.0, SECTION_SIZE_FT / 2.0)


def extract_docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        data = zf.read('word/document.xml')
    root = ET.fromstring(data)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paras = []
    for p in root.findall('.//w:p', ns):
        texts = [t.text or '' for t in p.findall('.//w:t', ns)]
        if texts:
            paras.append(''.join(texts))
    return '\n'.join(paras)


def first_course_clause(text: str) -> str:
    norm = normalize_text(text)
    if ' POB ' in f' {norm} ':
        tail = norm.split(' POB ', 1)[1]
    elif 'BEGIN AT' in norm:
        tail = norm.split('BEGIN AT', 1)[1]
    else:
        tail = norm
    parts = re.split(r'\bTHENCE\b|;', tail, flags=re.I)
    for part in parts:
        p = part.strip(' ,.')
        if 'DISTANCE OF' in p or 'A DISTANCE OF' in p:
            return p
    return parts[0].strip(' ,.') if parts else norm


def start_azimuth_from_clause(clause: str) -> float:
    s = normalize_text(clause)
    for word in ['NORTHEASTERLY', 'NORTHWESTERLY', 'SOUTHEASTERLY', 'SOUTHWESTERLY', 'NORTHERLY', 'SOUTHERLY', 'EASTERLY', 'WESTERLY']:
        if word in s:
            return CARDINAL_MAP[word]
    if 'ALONG THE EAST LINE' in s or 'ALONG THE WEST LINE' in s:
        if 'NORTH' in s:
            return 0.0
        return 180.0
    if 'ALONG THE NORTH LINE' in s or 'ALONG THE SOUTH LINE' in s:
        if 'WEST' in s:
            return 270.0
        return 90.0
    return 180.0


def split_deed_clauses(text: str):
    norm = normalize_text(text)
    if ' COMMENCE AT ' in f' {norm} ' and ' POB ' in f' {norm} ':
        tail = norm.split(' POB ', 1)[1]
    elif 'BEGIN AT' in norm:
        tail = norm.split('BEGIN AT', 1)[1]
    else:
        tail = norm
    tail = tail.strip(' ;,.')
    return [p.strip(' ,.') for p in re.split(r'\bTHENCE\b|;', tail, flags=re.I) if p and p.strip(' ,.')]




def parse_curves(clause: str):
    curves = []
    for m in CURVE_RE.finditer(clause):
        curves.append({
            'dir': 'R' if m.group(1).upper() == 'RIGHT' else 'L',
            'radius': float(m.group(2)),
            'delta_deg': parse_dms(m.group(3)),
        })
    return curves


def extract_line_control(clause: str):
    s = normalize_text(clause)
    dir_word = None
    for word in ['NORTHEASTERLY', 'NORTHWESTERLY', 'SOUTHEASTERLY', 'SOUTHWESTERLY', 'NORTHERLY', 'SOUTHERLY', 'EASTERLY', 'WESTERLY']:
        if re.search(rf'{word}', s):
            dir_word = word
            break
    if dir_word is None:
        m = re.search(r'IN\s+AN?\s+(NORTH|SOUTH|EAST|WEST)\s+\w*DIRECTION', s)
        if m:
            dir_word = m.group(1)

    fam = None
    if 'ALONG THE EAST LINE' in s or 'ALONG THE WEST LINE' in s:
        fam = 'NS'
    elif 'ALONG THE NORTH LINE' in s or 'ALONG THE SOUTH LINE' in s or 'NORTH LINE OF' in s or 'SOUTH LINE OF' in s:
        fam = 'EW'
    elif 'ALONG SAID 1/4- 1/4 SECTION LINE' in s or 'ALONG SAID 1/4-1/4 SECTION LINE' in s or 'ALONG SAID SECTION LINE' in s:
        # infer family from travel wording when the deed says only 'section line'
        if dir_word and ('EAST' in dir_word or 'WEST' in dir_word):
            fam = 'EW'
        elif dir_word and (dir_word.startswith('NORTH') or dir_word.startswith('SOUTH')):
            fam = 'NS'
    if 'CONTINUE ALONG THE PREVIOUS COURSE' in s and fam is None:
        if 'NORTH LINE' in s or 'SOUTH LINE' in s:
            fam = 'EW'
        elif 'EAST LINE' in s or 'WEST LINE' in s:
            fam = 'NS'

    if fam:
        d = None
        if dir_word:
            if fam == 'EW':
                if 'EAST' in dir_word:
                    d = 'E'
                elif 'WEST' in dir_word:
                    d = 'W'
            elif fam == 'NS':
                if dir_word.startswith('NORTH'):
                    d = 'N'
                elif dir_word.startswith('SOUTH'):
                    d = 'S'
        return fam, d
    return None, None


def solve_steps_with_locks(start_az_deg: float, steps: list):
    az = wrap360(start_az_deg)
    E = N = 0.0
    points = [(E, N)]
    family_base = {'NS_N': None, 'EW_E': None}

    def az_from_family(fam, d, current_az=None):
        if fam == 'NS' and family_base['NS_N'] is not None:
            if d == 'N':
                return family_base['NS_N']
            if d == 'S':
                return wrap360(family_base['NS_N'] + 180.0)
            if current_az is not None:
                north = family_base['NS_N']
                south = wrap360(north + 180.0)
                return north if abs(((current_az - north + 180) % 360) - 180) <= abs(((current_az - south + 180) % 360) - 180) else south
        if fam == 'EW' and family_base['EW_E'] is not None:
            if d == 'E':
                return family_base['EW_E']
            if d == 'W':
                return wrap360(family_base['EW_E'] + 180.0)
            if current_az is not None:
                east = family_base['EW_E']
                west = wrap360(east + 180.0)
                return east if abs(((current_az - east + 180) % 360) - 180) <= abs(((current_az - west + 180) % 360) - 180) else west
        return None

    def update_family(fam, d, current_az):
        if fam == 'NS':
            family_base['NS_N'] = current_az if d == 'N' else wrap360(current_az + 180.0)
        elif fam == 'EW':
            family_base['EW_E'] = current_az if d == 'E' else wrap360(current_az + 180.0)

    for s in steps:
        t = s['type'].lower()
        if t == 'turn':
            sign = 1.0 if s['side'].upper().startswith('R') else -1.0
            az = wrap360(az + sign * float(s['angle_deg']))
        elif t == 'line':
            fam = s.get('line_family')
            d = s.get('line_dir')
            locked = az_from_family(fam, d, az) if fam else None
            if locked is not None:
                az = locked
            elif fam and d:
                update_family(fam, d, az)
            elif fam and d is None:
                # continue along previous course, but keep the family orientation consistent with current az
                if fam == 'NS':
                    family_base['NS_N'] = az if (az <= 90 or az >= 270) else wrap360(az + 180.0)
                elif fam == 'EW':
                    family_base['EW_E'] = az if (0 < az < 180) else wrap360(az + 180.0)
            dE, dN = line_delta(float(s['dist']), az)
            E += dE
            N += dN
            points.append((E, N))
            if fam and d and locked is not None:
                update_family(fam, d, az)
        elif t == 'curve':
            pts, az = curve_points(E, N, az, float(s['radius']), float(s['delta_deg']), s['dir'], n=90)
            for p in pts[1:]:
                points.append(p)
            E, N = points[-1]
        else:
            raise ValueError(f'Unknown step type: {t}')

    end_E, end_N = points[-1]
    misclosure = math.hypot(end_E - points[0][0], end_N - points[0][1])
    total_len = 0.0
    for s in steps:
        if s['type'] == 'line':
            total_len += float(s['dist'])
        elif s['type'] == 'curve':
            total_len += float(s.get('arc', float(s['radius']) * math.radians(float(s['delta_deg']))))
    ratio = (total_len / misclosure) if misclosure > 0 else float('inf')
    summary = (
        'Closure summary\n'
        f'End point Easting  {end_E:.4f}\n'
        f'End point Northing {end_N:.4f}\n'
        f'Linear misclosure  {misclosure:.4f}\n'
        f'Total length       {total_len:.4f}\n'
        f'Relative precision 1:{ratio:,.0f}\n'
        f'End azimuth        {az:.6f}\n'
    )
    return {'points': points, 'summary': summary}

def parse_curve(clause: str):
    curves = parse_curves(clause)
    return curves[0] if curves else None


def parse_turn(clause: str):
    m = TURN_RE.search(clause)
    if not m:
        return None
    return {'side': 'R' if m.group(2).upper() == 'RIGHT' else 'L', 'angle_deg': parse_dms(m.group(1)), 'note': 'angle measured to tangent' if TANGENT_NOTE_RE.search(clause) else ''}


def parse_distance(clause: str):
    m = DIST_RE.search(clause)
    return float(m.group(1)) if m else None


def parse_narrative_steps(text: str):
    clauses = split_deed_clauses(text)
    steps = []
    log_lines = []
    pending_curve = None
    curve_count = 0
    for idx, clause in enumerate(clauses, start=1):
        p = clause.strip()
        p_up = p.upper()
        if not p:
            continue
        turn = parse_turn(p)
        dist = parse_distance(p)
        curves = parse_curves(p)
        curve = curves[0] if curves else None
        along_arc = bool(ALONG_ARC_RE.search(p_up))
        fam, ldir = extract_line_control(p)

        if along_arc and pending_curve and turn:
            steps.append({'type': 'turn', **turn, 'clause_index': idx, 'raw_clause': p})
            log_lines.append(f'{idx}. Turn {turn["side"]}, angle {turn["angle_deg"]:.8f} {turn.get("note", "")}'.strip())

        if along_arc and pending_curve:
            arc = dist if dist is not None else pending_curve['radius'] * math.radians(pending_curve['delta_deg'])
            steps.append({'type': 'curve', **pending_curve, 'arc': arc, 'clause_index': idx, 'raw_clause': p})
            log_lines.append(f'{idx}. Curve {pending_curve["dir"]}, R {pending_curve["radius"]}, delta {pending_curve["delta_deg"]:.8f}, arc {arc}')
            pending_curve = None
            curve_count += 1
            if curves:
                pending_curve = curves[-1]
                log_lines.append(f'{idx}. Curve parameters saved {pending_curve["dir"]}, R {pending_curve["radius"]}, delta {pending_curve["delta_deg"]:.8f}')
            continue

        if turn:
            steps.append({'type': 'turn', **turn, 'clause_index': idx, 'raw_clause': p})
            log_lines.append(f'{idx}. Turn {turn["side"]}, angle {turn["angle_deg"]:.8f} {turn.get("note", "")}'.strip())

        if dist is not None and not along_arc:
            line_step = {'type': 'line', 'dist': dist, 'clause_index': idx, 'raw_clause': p}
            if fam and ldir:
                line_step['line_family'] = fam
                line_step['line_dir'] = ldir
            steps.append(line_step)
            log_lines.append(f'{idx}. Line dist {dist}' + (f' [{fam}:{ldir}]' if fam and ldir else ''))

        if curve:
            if along_arc:
                arc = dist if dist is not None else curve['radius'] * math.radians(curve['delta_deg'])
                steps.append({'type': 'curve', **curve, 'arc': arc, 'clause_index': idx, 'raw_clause': p})
                log_lines.append(f'{idx}. Curve {curve["dir"]}, R {curve["radius"]}, delta {curve["delta_deg"]:.8f}, arc {arc}')
                curve_count += 1
            else:
                pending_curve = curve
                log_lines.append(f'{idx}. Curve parameters saved {curve["dir"]}, R {curve["radius"]}, delta {curve["delta_deg"]:.8f}')

    if pending_curve is not None:
        log_lines.append('Pending curve parameters remained unresolved at end of deed.')

    if not steps:
        raise ValueError('No angle deed steps were parsed.')
    return steps, 'Parse log\n' + '\n'.join(log_lines), curve_count


def build_debug_report(start_az_deg: float, steps: list, solved: dict) -> str:
    az = wrap360(start_az_deg)
    E = 0.0
    N = 0.0
    family_base = {'NS_N': None, 'EW_E': None}
    lines = []
    lines.append('Geometry debug report')
    lines.append(f'Start azimuth: {az:.6f}')
    lines.append('')
    step_no = 0

    def az_from_family(fam, d, current_az=None):
        if fam == 'NS' and family_base['NS_N'] is not None:
            if d == 'N':
                return family_base['NS_N']
            if d == 'S':
                return wrap360(family_base['NS_N'] + 180.0)
            if current_az is not None:
                north = family_base['NS_N']
                south = wrap360(north + 180.0)
                return north if abs(((current_az - north + 180) % 360) - 180) <= abs(((current_az - south + 180) % 360) - 180) else south
        if fam == 'EW' and family_base['EW_E'] is not None:
            if d == 'E':
                return family_base['EW_E']
            if d == 'W':
                return wrap360(family_base['EW_E'] + 180.0)
            if current_az is not None:
                east = family_base['EW_E']
                west = wrap360(east + 180.0)
                return east if abs(((current_az - east + 180) % 360) - 180) <= abs(((current_az - west + 180) % 360) - 180) else west
        return None

    def update_family(fam, d, current_az):
        if fam == 'NS':
            family_base['NS_N'] = current_az if d == 'N' else wrap360(current_az + 180.0)
        elif fam == 'EW':
            family_base['EW_E'] = current_az if d == 'E' else wrap360(current_az + 180.0)

    for s in steps:
        t = s['type'].lower()
        if t == 'turn':
            step_no += 1
            az_in = az
            sign = 1.0 if s['side'].upper().startswith('R') else -1.0
            az = wrap360(az + sign * float(s['angle_deg']))
            lines.append(f'{step_no}. TURN | clause {s.get("clause_index", "?")} | side {s.get("side")} | angle {float(s.get("angle_deg",0.0)):.8f} | in {az_in:.6f} | out {az:.6f} | note {s.get("note","")}')
            lines.append(f'   raw: {s.get("raw_clause","")}')
        elif t == 'line':
            step_no += 1
            dist = float(s['dist'])
            fam = s.get('line_family')
            d = s.get('line_dir')
            locked = az_from_family(fam, d, az) if fam else None
            az_before = az
            if locked is not None:
                az = locked
            elif fam and d:
                update_family(fam, d, az)
            elif fam and d is None:
                if fam == 'NS':
                    family_base['NS_N'] = az if (az <= 90 or az >= 270) else wrap360(az + 180.0)
                elif fam == 'EW':
                    family_base['EW_E'] = az if (0 < az < 180) else wrap360(az + 180.0)
            dE, dN = line_delta(dist, az)
            E2 = E + dE
            N2 = N + dN
            lock_note = f' | lock {fam}:{d} | az before {az_before:.6f}' if fam and d else ''
            lines.append(f'{step_no}. LINE | clause {s.get("clause_index", "?")} | az {az:.6f} | dist {dist:.4f} | start ({E:.4f}, {N:.4f}) | end ({E2:.4f}, {N2:.4f}){lock_note}')
            lines.append(f'   raw: {s.get("raw_clause","")}')
            E, N = E2, N2
            if fam and d and locked is not None:
                update_family(fam, d, az)
        elif t == 'curve':
            step_no += 1
            pts, az_out = curve_points(E, N, az, float(s['radius']), float(s['delta_deg']), s['dir'], n=90)
            E2, N2 = pts[-1]
            arc = float(s.get('arc', float(s['radius']) * math.radians(float(s['delta_deg']))))
            lines.append(f'{step_no}. CURVE | clause {s.get("clause_index", "?")} | dir {s.get("dir")} | R {float(s.get("radius",0.0)):.4f} | delta {float(s.get("delta_deg",0.0)):.8f} | arc {arc:.4f} | tan in {az:.6f} | tan out {az_out:.6f} | end ({E2:.4f}, {N2:.4f})')
            lines.append(f'   raw: {s.get("raw_clause","")}')
            E, N = E2, N2
            az = az_out
    lines.append('')
    lines.append('Closure summary')
    lines.extend((solved.get('summary') or '').splitlines())
    return '\n'.join(lines)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title('Schoel PLSS Angle Deed Locator'))
        self.geometry('1320x940')
        self.minsize(1180, 820)
        apply_theme(self)
        self.aliquot_chains = []
        self.begin_ref = {}
        self.relative_points = []
        self.absolute_points = []
        self.solve_summary = {'line_count': 0, 'curve_count': 0}
        self.parse_log = ''
        self.debug_report = ''

        body = make_scrolled_body(self)
        make_header(body, 'Schoel PLSS Angle Deed Locator', 'Paste or import an angle-based PLSS deed. This module is separate from the Bearing Deed Plotter, Interior Angle Deed Plotter, and the existing PLSS Deed Locator.')

        input_sec = section(body, 'Deed Input')
        btnrow = ttk.Frame(input_sec)
        btnrow.pack(fill='x', pady=(0, 8))
        ttk.Button(btnrow, text='Import TXT or DOCX', command=self.import_file, style='Primary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Parse and Draw', command=self.parse_and_draw, style='Accent.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Copy Summary', command=self.copy_summary, style='Primary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Copy Parse Log', command=self.copy_log, style='Primary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Copy Debug Report', command=self.copy_debug, style='Primary.TButton').pack(side='left', padx=(0, 6))
        self.input_box = text_box(input_sec, width=120, height=16)
        self.input_box.pack(fill='both', expand=True)

        summary_sec = section(body, 'Parsed Summary')
        self.summary_var = tk.StringVar(value='Paste an angle-based PLSS deed and click Parse and Draw.')
        ttk.Label(summary_sec, textvariable=self.summary_var, wraplength=1220, justify='left').pack(anchor='w')

        vis_wrap = ttk.Frame(body)
        vis_wrap.pack(fill='both', expand=True)
        left = section(vis_wrap, 'Section Location View')
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))
        right = section(vis_wrap, 'Relative Angle Deed Plot')
        right.pack(side='left', fill='both', expand=True)
        self.section_canvas = tk.Canvas(left, bg='white', width=560, height=560, highlightthickness=1, highlightbackground=COLORS['line'])
        self.section_canvas.pack(fill='both', expand=True)
        self.plot_canvas = tk.Canvas(right, bg='white', width=560, height=560, highlightthickness=1, highlightbackground=COLORS['line'])
        self.plot_canvas.pack(fill='both', expand=True)

        notes = section(body, 'What This Module Reads')
        ttk.Label(notes, text=(
            'Reads PLSS aliquot containers, begin or commence corner references, interior-angle narrative deeds, and curve language including radius, central angle, PT, PC, PCC, PRC, and angle measured to tangent. '
            'This build keeps section placement in survey coordinates so aliquot tracts like NE 1/4 of SE 1/4 draw in the southeast quarter instead of the northeast quarter of the section.'
        ), wraplength=1220, justify='left').pack(anchor='w')

        self.draw_section_grid()
        self.draw_plot([])

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[('Supported Files', '*.txt *.docx'), ('Text Files', '*.txt'), ('Word Files', '*.docx'), ('All Files', '*.*')])
        if not path:
            return
        try:
            data = extract_docx_text(path) if path.lower().endswith('.docx') else open(path, 'r', encoding='utf-8', errors='ignore').read()
            self.input_box.delete('1.0', 'end')
            self.input_box.insert('1.0', data)
        except Exception as e:
            messagebox.showerror('Import', str(e))

    def copy_summary(self):
        copy_to_clipboard(self, self.summary_var.get())
        messagebox.showinfo('Copied', 'Summary copied to clipboard.')

    def copy_log(self):
        copy_to_clipboard(self, self.parse_log)
        messagebox.showinfo('Copied', 'Parse log copied to clipboard.')

    def copy_debug(self):
        copy_to_clipboard(self, self.debug_report)
        messagebox.showinfo('Copied', 'Debug report copied to clipboard.')

    def parse_and_draw(self):
        text = self.input_box.get('1.0', 'end').strip()
        if not text:
            messagebox.showwarning('PLSS Angle Deed Locator', 'Paste deed text first.')
            return
        sec, twp, rng = find_section_info(text)
        state = find_state(text)
        self.aliquot_chains = parse_aliquot_chains(text)
        self.begin_ref = extract_beginning_reference(text, self.aliquot_chains)
        try:
            steps, self.parse_log, parsed_curve_count = parse_narrative_steps(text)
            start_az = start_azimuth_from_clause(first_course_clause(text))
            solved = solve_steps_with_locks(start_az, steps)
            self.relative_points = solved['points']
            self.debug_report = build_debug_report(start_az, steps, solved)
            self.solve_summary = {
                'line_count': sum(1 for s in steps if s['type'] == 'line'),
                'curve_count': sum(1 for s in steps if s['type'] == 'curve'),
                'parsed_curve_count': parsed_curve_count,
                'step_count': len(steps),
                'closure': solved['summary'],
            }
        except Exception as e:
            self.relative_points = []
            self.solve_summary = {'line_count': 0, 'curve_count': 0, 'parsed_curve_count': 0, 'step_count': 0, 'closure': str(e)}
            self.parse_log = f'Parse failure\n{e}'
            self.debug_report = self.parse_log

        self.absolute_points = []
        start = None
        if self.begin_ref.get('ref_chain') and self.begin_ref.get('ref_corner'):
            start = point_for_corner(rect_to_feet(self.begin_ref['ref_chain']['rect']), self.begin_ref['ref_corner'])
        elif self.begin_ref.get('quarter_corner'):
            start = section_point_for_quarter_corner(self.begin_ref['quarter_corner'])
        elif self.aliquot_chains:
            start = point_for_corner(rect_to_feet(self.aliquot_chains[0]['rect']), 'SW')
        if start and self.relative_points:
            x0, y0 = self.relative_points[0]
            dx = start[0] - x0
            dy = start[1] - y0
            self.absolute_points = [(x + dx, y + dy) for x, y in self.relative_points]

        lines = [
            f'State: {state or "Not found"}',
            f'Section: {sec if sec is not None else "Not found"}',
            f'Township: {twp or "Not found"}',
            f'Range: {rng or "Not found"}',
            f'Aliquot locations found: {len(self.aliquot_chains)}',
        ]
        if self.aliquot_chains:
            for i, ch in enumerate(self.aliquot_chains[:10], start=1):
                lines.append(f'  {i}. {ch["text"]}')
        lines.append(f'Begin or commence clause found: {"Yes" if self.begin_ref.get("clause") else "No"}')
        if self.begin_ref.get('ref_chain'):
            lines.append(f'Begin tract: {self.begin_ref["ref_chain"]["text"]}')
        if self.begin_ref.get('ref_corner'):
            lines.append(f'Begin corner: {self.begin_ref["ref_corner"]}')
        if self.begin_ref.get('quarter_corner'):
            lines.append(f'Quarter corner: {self.begin_ref["quarter_corner"]}')
        lines.append(f'Solved steps: {self.solve_summary.get("step_count", 0)}')
        lines.append(f'Line steps: {self.solve_summary["line_count"]}')
        lines.append(f'Curve steps: {self.solve_summary["curve_count"]}')
        if self.absolute_points:
            lines.append(f'Section placement points drawn: {len(self.absolute_points)}')
        else:
            lines.append('Section placement note: A begin or commence corner tie was not strong enough to place the tract inside the section view.')
        lines.append('Closure report:')
        lines.extend((self.solve_summary.get('closure') or '').splitlines()[:6])
        lines.append('Use Copy Debug Report to see per-call azimuths, curves, and end coordinates.')
        self.summary_var.set('\n'.join(lines))
        self.draw_section_grid()
        self.draw_plot(self.relative_points)

    def draw_section_grid(self):
        c = self.section_canvas
        c.delete('all')
        w = max(200, c.winfo_width() or 560)
        h = max(200, c.winfo_height() or 560)
        pad = 40

        world_minx, world_miny = 0.0, 0.0
        world_maxx, world_maxy = SECTION_SIZE_FT, SECTION_SIZE_FT
        if self.absolute_points:
            xs = [p[0] for p in self.absolute_points]
            ys = [p[1] for p in self.absolute_points]
            world_minx = min(world_minx, min(xs))
            world_miny = min(world_miny, min(ys))
            world_maxx = max(world_maxx, max(xs))
            world_maxy = max(world_maxy, max(ys))

        margin_x = max(SECTION_SIZE_FT * 0.10, (world_maxx - world_minx) * 0.08)
        margin_y = max(SECTION_SIZE_FT * 0.10, (world_maxy - world_miny) * 0.08)
        world_minx -= margin_x
        world_maxx += margin_x
        world_miny -= margin_y
        world_maxy += margin_y

        dx = max(world_maxx - world_minx, 1.0)
        dy = max(world_maxy - world_miny, 1.0)
        scale = min((w - 2 * pad) / dx, (h - 2 * pad) / dy)

        def sx(ft):
            return pad + (ft - world_minx) * scale

        def sy(ft):
            return h - pad - (ft - world_miny) * scale

        sec_ix0 = math.floor(world_minx / SECTION_SIZE_FT)
        sec_ix1 = math.floor((world_maxx - 1e-9) / SECTION_SIZE_FT)
        sec_iy0 = math.floor(world_miny / SECTION_SIZE_FT)
        sec_iy1 = math.floor((world_maxy - 1e-9) / SECTION_SIZE_FT)

        for ix in range(sec_ix0, sec_ix1 + 1):
            for iy in range(sec_iy0, sec_iy1 + 1):
                bx0 = ix * SECTION_SIZE_FT
                by0 = iy * SECTION_SIZE_FT
                bx1 = bx0 + SECTION_SIZE_FT
                by1 = by0 + SECTION_SIZE_FT
                outline = 'black' if (ix == 0 and iy == 0) else COLORS['line']
                width = 2 if (ix == 0 and iy == 0) else 1
                c.create_rectangle(sx(bx0), sy(by1), sx(bx1), sy(by0), outline=outline, width=width)
                mx = (bx0 + bx1) / 2.0
                my = (by0 + by1) / 2.0
                c.create_line(sx(mx), sy(by1), sx(mx), sy(by0), fill=COLORS['primary'], width=2 if (ix == 0 and iy == 0) else 1)
                c.create_line(sx(bx0), sy(my), sx(bx1), sy(my), fill=COLORS['primary'], width=2 if (ix == 0 and iy == 0) else 1)
                for frac in [0.25, 0.75]:
                    xx = bx0 + frac * SECTION_SIZE_FT
                    c.create_line(sx(xx), sy(by1), sx(xx), sy(by0), fill=COLORS['line'], dash=(4, 3))
                for frac in [0.25, 0.75]:
                    yy = by0 + frac * SECTION_SIZE_FT
                    c.create_line(sx(bx0), sy(yy), sx(bx1), sy(yy), fill=COLORS['line'], dash=(4, 3))
                if ix == 0 and iy == 0:
                    c.create_text(sx((bx0 + mx) / 2), sy((my + by1) / 2), text='NW', font=('Segoe UI', 12, 'bold'))
                    c.create_text(sx((mx + bx1) / 2), sy((my + by1) / 2), text='NE', font=('Segoe UI', 12, 'bold'))
                    c.create_text(sx((bx0 + mx) / 2), sy((by0 + my) / 2), text='SW', font=('Segoe UI', 12, 'bold'))
                    c.create_text(sx((mx + bx1) / 2), sy((by0 + my) / 2), text='SE', font=('Segoe UI', 12, 'bold'))
                    for x, y in [(bx0, by0), (bx1, by0), (bx0, by1), (bx1, by1)]:
                        c.create_oval(sx(x) - 4, sy(y) - 4, sx(x) + 4, sy(y) + 4, fill='black')
                    for x, y in [(mx, by0), (mx, by1), (bx0, my), (bx1, my), (mx, my)]:
                        c.create_oval(sx(x) - 3, sy(y) - 3, sx(x) + 3, sy(y) + 3, fill=COLORS['accent'], outline='')

        for idx, ch in enumerate(self.aliquot_chains):
            rx0, ry0, rx1, ry1 = rect_to_feet(ch['rect'])
            fill = '#dce4b7' if idx == 0 else '#f8d7bf'
            c.create_rectangle(sx(rx0), sy(ry1), sx(rx1), sy(ry0), fill=fill, outline=COLORS['accent'], width=2, stipple='gray25')

        if self.absolute_points and len(self.absolute_points) >= 2:
            flat = []
            for x, y in self.absolute_points:
                flat.extend([sx(x), sy(y)])
            c.create_line(*flat, fill=COLORS['primary_dark'], width=3)
            bx, by = self.absolute_points[0]
            ex, ey = self.absolute_points[-1]
            c.create_oval(sx(bx) - 5, sy(by) - 5, sx(bx) + 5, sy(by) + 5, fill=COLORS['accent'], outline='')
            c.create_text(sx(bx) + 8, sy(by) - 8, text='BEGIN', anchor='w', font=('Segoe UI', 8, 'bold'))
            c.create_oval(sx(ex) - 4, sy(ey) - 4, sx(ex) + 4, sy(ey) + 4, fill=COLORS['primary_dark'], outline='')
            c.create_text(sx(ex) + 8, sy(ey) + 8, text='END', anchor='w', font=('Segoe UI', 8, 'bold'))

        c.create_text(w / 2, 18, text='Section View with angle-deed tract placement', font=('Segoe UI', 10, 'bold'), fill=COLORS['text'])

    def draw_plot(self, pts):
        c = self.plot_canvas
        c.delete('all')
        w = max(200, c.winfo_width() or 560)
        h = max(200, c.winfo_height() or 560)
        pad = 40
        c.create_text(w / 2, 18, text='Relative Angle Deed Plot', font=('Segoe UI', 10, 'bold'), fill=COLORS['text'])
        if not pts or len(pts) < 2:
            c.create_text(w / 2, h / 2, text='No plottable angle deed calls recognized.', font=('Segoe UI', 12), fill=COLORS['muted'])
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 1.0)
        dy = max(maxy - miny, 1.0)
        scale = min((w - 2 * pad) / dx, (h - 2 * pad) / dy)
        def tx(x):
            return pad + (x - minx) * scale
        def ty(y):
            return h - pad - (y - miny) * scale
        c.create_rectangle(pad, pad, w - pad, h - pad, outline=COLORS['line'])
        flat = []
        for x, y in pts:
            flat.extend([tx(x), ty(y)])
        c.create_line(*flat, fill=COLORS['primary_dark'], width=3)
        for i, (x, y) in enumerate(pts):
            X, Y = tx(x), ty(y)
            fill = COLORS['accent'] if i == 0 else COLORS['primary']
            c.create_oval(X - 4, Y - 4, X + 4, Y + 4, fill=fill, outline='')
            if i < 50:
                c.create_text(X + 8, Y - 8, text=str(i + 1), anchor='w', font=('Segoe UI', 8))
        c.create_line(w - 30, h - 60, w - 30, h - 100, arrow='last', width=2)
        c.create_text(w - 30, h - 110, text='N', font=('Segoe UI', 10, 'bold'))


def run():
    App().mainloop()


def main():
    run()

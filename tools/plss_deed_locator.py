import math
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, copy_to_clipboard, COLORS
from geometry_utils import parse_bearing, azimuth_to_ne_delta

SECTION_SIZE_FT = 5280.0

SECTION_PATTERNS = [
    re.compile(r'\bSECTION\s+(\d{1,2})\b', re.I),
    re.compile(r'\bSEC\.?\s*(\d{1,2})\b', re.I),
    re.compile(r'\bS\.?\s*(\d{1,2})\b(?=.*\bT(?:OWNSHIP)?\b)', re.I),
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
    re.compile(r'\bALABAMA\b', re.I), re.compile(r'\bMISSISSIPPI\b', re.I), re.compile(r'\bARKANSAS\b', re.I),
    re.compile(r'\bLOUISIANA\b', re.I), re.compile(r'\bFLORIDA\b', re.I), re.compile(r'\bGEORGIA\b', re.I),
    re.compile(r'\bTENNESSEE\b', re.I), re.compile(r'\bTEXAS\b', re.I), re.compile(r'\bOKLAHOMA\b', re.I),
    re.compile(r'\bKANSAS\b', re.I), re.compile(r'\bCOLORADO\b', re.I), re.compile(r'\bNEBRASKA\b', re.I),
    re.compile(r'\bNORTH DAKOTA\b', re.I), re.compile(r'\bSOUTH DAKOTA\b', re.I), re.compile(r'\bMONTANA\b', re.I),
    re.compile(r'\bWYOMING\b', re.I), re.compile(r'\bNEW MEXICO\b', re.I), re.compile(r'\bUTAH\b', re.I),
    re.compile(r'\bIDAHO\b', re.I), re.compile(r'\bWASHINGTON\b', re.I), re.compile(r'\bOREGON\b', re.I),
    re.compile(r'\bCALIFORNIA\b', re.I), re.compile(r'\bARIZONA\b', re.I), re.compile(r'\bMINNESOTA\b', re.I),
    re.compile(r'\bIOWA\b', re.I), re.compile(r'\bMISSOURI\b', re.I), re.compile(r'\bILLINOIS\b', re.I),
    re.compile(r'\bINDIANA\b', re.I), re.compile(r'\bOHIO\b', re.I), re.compile(r'\bMICHIGAN\b', re.I),
    re.compile(r'\bWISCONSIN\b', re.I),
]


def normalize_text(text: str) -> str:
    t = text.upper()
    replacements = {
        '¼': ' 1/4 ', '½': ' 1/2 ', '¾': ' 3/4 ',
        'NORTHWESTERLY': ' NORTHWESTERLY ', 'NORTHEASTERLY': ' NORTHEASTERLY ',
        'SOUTHEASTERLY': ' SOUTHEASTERLY ', 'SOUTHWESTERLY': ' SOUTHWESTERLY ',
        'N.E.': ' NE ', 'N.W.': ' NW ', 'S.E.': ' SE ', 'S.W.': ' SW ',
        'NORTHEAST QUARTER': ' NE 1/4 ', 'NORTHWEST QUARTER': ' NW 1/4 ',
        'SOUTHEAST QUARTER': ' SE 1/4 ', 'SOUTHWEST QUARTER': ' SW 1/4 ',
        'NORTHEAST ONE-QUARTER': ' NE 1/4 ', 'NORTHWEST ONE-QUARTER': ' NW 1/4 ',
        'SOUTHEAST ONE-QUARTER': ' SE 1/4 ', 'SOUTHWEST ONE-QUARTER': ' SW 1/4 ',
        'NORTH HALF': ' N 1/2 ', 'SOUTH HALF': ' S 1/2 ', 'EAST HALF': ' E 1/2 ', 'WEST HALF': ' W 1/2 ',
        'NORTH ONE-HALF': ' N 1/2 ', 'SOUTH ONE-HALF': ' S 1/2 ', 'EAST ONE-HALF': ' E 1/2 ', 'WEST ONE-HALF': ' W 1/2 ',
        'TRUE POINT OF BEGINNING': ' POB ', 'POINT OF BEGINNING': ' POB ',
        'COMMENCING AT': ' COMMENCE AT ', 'COMMENCING FROM': ' COMMENCE FROM ',
        'RIGHT-OF-WAY': ' RIGHT OF WAY ',
        ' DEGREES ': ' DEG ', ' DEGREE ': ' DEG ',
        ' MINUTES ': ' MIN ', ' MINUTE ': ' MIN ',
        ' SECONDS ': ' SEC ', ' SECOND ': ' SEC ',
    }
    for a, b in replacements.items():
        t = t.replace(a, b)
    t = re.sub(r'[“”]', '"', t)
    t = re.sub(r"[‘’]", "'", t)
    # normalize quarter and half after directional words where not already handled
    t = re.sub(r'\b(NORTH|SOUTH|EAST|WEST)\s+1/2\b', lambda m: f" {m.group(1)[0]} 1/2 ", t)
    t = re.sub(r'\b(NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST)\s+1/4\b', lambda m: f" {m.group(1)[:2].replace('NO','N').replace('SO','S')} 1/4 ", t)
    t = re.sub(r'\bNORTHEAST\b', ' NE ', t)
    t = re.sub(r'\bNORTHWEST\b', ' NW ', t)
    t = re.sub(r'\bSOUTHEAST\b', ' SE ', t)
    t = re.sub(r'\bSOUTHWEST\b', ' SW ', t)
    t = re.sub(r'\bNORTH\b', ' NORTH ', t)
    t = re.sub(r'\bSOUTH\b', ' SOUTH ', t)
    t = re.sub(r'\bEAST\b', ' EAST ', t)
    t = re.sub(r'\bWEST\b', ' WEST ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def normalize_dir(word: str) -> str:
    word = word.upper()
    return {'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W'}.get(word, word)


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
                rect = [x0, y0, mx, my]
            elif token == 'NE':
                rect = [mx, y0, x1, my]
            elif token == 'SW':
                rect = [x0, my, mx, y1]
            elif token == 'SE':
                rect = [mx, my, x1, y1]
        elif frac == '1/2':
            if token == 'N':
                rect = [x0, y0, x1, my]
            elif token == 'S':
                rect = [x0, my, x1, y1]
            elif token == 'E':
                rect = [mx, y0, x1, y1]
            elif token == 'W':
                rect = [x0, y0, mx, y1]
    return rect


def rect_union(rects):
    if not rects:
        return None
    return [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]


def rect_to_feet(rect):
    return [rect[0] * SECTION_SIZE_FT, rect[1] * SECTION_SIZE_FT, rect[2] * SECTION_SIZE_FT, rect[3] * SECTION_SIZE_FT]


def point_for_corner(rect_ft, corner):
    x0, y0, x1, y1 = rect_ft
    corner = corner.upper()
    mapping = {
        'NW': (x0, y0), 'NE': (x1, y0), 'SW': (x0, y1), 'SE': (x1, y1),
        'N': ((x0 + x1) / 2.0, y0), 'S': ((x0 + x1) / 2.0, y1),
        'W': (x0, (y0 + y1) / 2.0), 'E': (x1, (y0 + y1) / 2.0),
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
            chains.append({
                'text': cand,
                'seq_raw': seq_raw,
                'seq': seq_outer_to_inner,
                'rect': rect_for_token_sequence(seq_outer_to_inner),
            })
    return chains


def parse_line_corner_refs(text: str):
    norm = normalize_text(text)
    refs = []
    for side_long, side_short in [('NORTH', 'N'), ('SOUTH', 'S'), ('EAST', 'E'), ('WEST', 'W')]:
        if re.search(rf'\b(ALONG|ON|TO|IN) THE {side_long} LINE OF\b|\b{side_long} LINE OF\b', norm):
            refs.append({'type': 'line', 'side': side_short})
    corner_map = {'NORTHWEST': 'NW', 'NORTHEAST': 'NE', 'SOUTHWEST': 'SW', 'SOUTHEAST': 'SE', 'NW': 'NW', 'NE': 'NE', 'SW': 'SW', 'SE': 'SE'}
    for long_name, short_name in corner_map.items():
        if re.search(rf'\b{long_name} CORNER\b', norm):
            refs.append({'type': 'corner', 'corner': short_name})
    for side in ('NORTH', 'SOUTH', 'EAST', 'WEST'):
        if re.search(rf'\b{side} QUARTER CORNER\b|\b{side[0]} QUARTER CORNER\b', norm):
            refs.append({'type': 'quarter_corner', 'side': side[0]})
    if 'QUARTER CORNER' in norm and not any(r.get('type') == 'quarter_corner' for r in refs):
        refs.append({'type': 'quarter_corner', 'side': '?'})
    if re.search(r'\bCENTER OF SECTION\b|\bCENTER SECTION\b|\bCENTER OF SAID SECTION\b', norm):
        refs.append({'type': 'center'})
    return refs


def parse_commencing_pob(text: str):
    norm = normalize_text(text)
    commencing = bool(re.search(r'\bCOMMENCE(?:D|S|)\s+(?:AT|FROM)\b', norm))
    pob = bool(re.search(r'\bPOB\b', norm))
    return commencing, pob


def _bearing_word_to_compact(bearing_text: str) -> str:
    t = normalize_text(bearing_text)
    m = re.search(r'\b(N|S|NORTH|SOUTH)\b\s*(\d{1,3})(?:\s*DEG)?(?:\s*(\d{1,2})(?:\s*MIN)?)?(?:\s*(\d{1,2}(?:\.\d+)?)(?:\s*SEC)?)?\s*(E|W|EAST|WEST)\b', t)
    if not m:
        return ''
    ns = normalize_dir(m.group(1))
    deg = m.group(2)
    minutes = m.group(3) or '0'
    seconds = m.group(4) or '0'
    ew = normalize_dir(m.group(5))
    return f'{ns} {deg} {minutes} {seconds} {ew}'


def extract_prose_calls(text: str, after_pob: bool = True):
    norm = normalize_text(text)
    work = norm
    if after_pob:
        pob_match = re.search(r'\bPOB\b', norm)
        if pob_match:
            work = norm[pob_match.end():]
    else:
        comm_match = re.search(r'\bCOMMENCE(?:D|S|)?\s+(?:AT|FROM)\b', norm)
        pob_match = re.search(r'\bPOB\b', norm)
        if comm_match and pob_match and pob_match.start() > comm_match.start():
            work = norm[comm_match.start():pob_match.start()]
        elif comm_match:
            work = norm[comm_match.start():]
    segments = re.split(r'\bTHENCE\b|;', work)
    calls = []
    line_pat = re.compile(
        r'\b(N|S|NORTH|SOUTH)\b\s*(\d{1,3})(?:\s*DEG)?(?:\s*(\d{1,2})(?:\s*MIN)?)?(?:\s*(\d{1,2}(?:\.\d+)?)(?:\s*SEC)?)?\s*\b(E|W|EAST|WEST)\b.*?\b(?:DISTANCE OF|A DISTANCE OF|DISTANCE|FOR|RUN)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:FEET|FOOT|FT|\')',
        re.I)
    curve_pat = re.compile(r'\bARC DISTANCE OF\s*([0-9]+(?:\.[0-9]+)?)\s*(?:FEET|FOOT|FT|\')\b', re.I)
    for seg in segments:
        seg = seg.strip(' ,.')
        if not seg:
            continue
        m = line_pat.search(seg)
        if m:
            bearing = _bearing_word_to_compact(m.group(0))
            dist = float(m.group(6))
            if bearing:
                calls.append((bearing, dist, 'line', seg))
                continue
        m2 = re.search(r'\b([NS])\s*(\d{1,3})[^\d]+(\d{1,2})?[^\d]+(\d{1,2}(?:\.\d+)?)?\s*([EW])\b', seg, re.I)
        d2 = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:FEET|FOOT|FT|\')', seg, re.I)
        if m2 and d2:
            bearing = f"{m2.group(1).upper()} {m2.group(2)} {m2.group(3) or 0} {m2.group(4) or 0} {m2.group(5).upper()}"
            calls.append((bearing, float(d2.group(1)), 'line', seg))
            continue
        c = curve_pat.search(seg)
        if c:
            calls.append(('', float(c.group(1)), 'curve', seg))
    return calls


def compute_plot_points_from_calls(calls, start_xy=(0.0, 0.0)):
    pts = [tuple(start_xy)]
    x, y = float(start_xy[0]), float(start_xy[1])
    line_count = 0
    curve_count = 0
    for bearing, dist, kind, _seg in calls:
        if kind == 'curve':
            curve_count += 1
            continue
        try:
            az = parse_bearing(bearing)
        except Exception:
            continue
        dn, de = azimuth_to_ne_delta(az, float(dist))
        y += dn
        x += de
        pts.append((x, y))
        line_count += 1
    return pts, line_count, curve_count


def compute_plot_points(text: str):
    calls = extract_prose_calls(text, after_pob=True)
    return compute_plot_points_from_calls(calls)


def parse_commencement_details(text: str, aliquot_chains):
    norm = normalize_text(text)
    comm_match = re.search(r'\bCOMMENCE(?:D|S|)?\s+(?:AT|FROM)\b(.+?)(?:\bPOB\b)', norm)
    clause = comm_match.group(1) if comm_match else ''
    if not clause:
        comm_match = re.search(r'\bCOMMENCE(?:D|S|)?\s+(?:AT|FROM)\b(.+)', norm)
        clause = comm_match.group(1) if comm_match else ''
    ref_corner = None
    ref_chain = None
    chain_lookup = {ch['text']: ch for ch in aliquot_chains}
    # longest chain inside commencement clause
    candidates = []
    clause_no_the = re.sub(r'\bTHE\b\s*', '', clause)
    clause_no_the = re.sub(r'\s+', ' ', clause_no_the).strip()
    for ch in aliquot_chains:
        if ch['text'] in clause_no_the:
            candidates.append(ch)
    if candidates:
        ref_chain = sorted(candidates, key=lambda c: len(c['text']), reverse=True)[0]
    m = re.search(r'\b(NW|NE|SW|SE|NORTHWEST|NORTHEAST|SOUTHWEST|SOUTHEAST)\s+CORNER\b', clause)
    if m:
        ref_corner = normalize_dir(m.group(1)) if len(m.group(1)) == 1 else m.group(1)[:2].replace('NO', 'N').replace('SO', 'S')
        mapping = {'NORTHEAST': 'NE', 'NORTHWEST': 'NW', 'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'}
        ref_corner = mapping.get(m.group(1).upper(), ref_corner)
    quarter_corner = None
    qm = re.search(r'\b(NORTH|SOUTH|EAST|WEST|N|S|E|W)\s+QUARTER\s+CORNER\b', clause)
    if qm:
        quarter_corner = normalize_dir(qm.group(1))
    tie_calls = extract_prose_calls(text, after_pob=False)
    return {
        'clause': clause,
        'ref_chain': ref_chain,
        'ref_corner': ref_corner,
        'quarter_corner': quarter_corner,
        'tie_calls': tie_calls,
    }


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
    return (SECTION_SIZE_FT / 2.0, 0.0)


def place_plot_in_section(text: str, aliquot_chains):
    details = parse_commencement_details(text, aliquot_chains)
    start = None
    if details['ref_chain'] and details['ref_corner']:
        sx, sy = point_for_corner(rect_to_feet(details['ref_chain']['rect']), details['ref_corner'])
        start = (sx, SECTION_SIZE_FT - sy)
    elif details['quarter_corner']:
        start = section_point_for_quarter_corner(details['quarter_corner'])
    elif aliquot_chains:
        sx, sy = point_for_corner(rect_to_feet(aliquot_chains[0]['rect']), 'SW')
        start = (sx, SECTION_SIZE_FT - sy)
    tract_calls = extract_prose_calls(text, after_pob=True)
    tie_pts = []
    abs_pts = []
    if start is not None:
        if details['tie_calls']:
            tie_pts, _, _ = compute_plot_points_from_calls(details['tie_calls'], start)
            start = tie_pts[-1]
        abs_pts, _, _ = compute_plot_points_from_calls(tract_calls, start)
    return details, tie_pts, abs_pts


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title('Schoel PLSS Deed Locator'))
        self.geometry('1320x940')
        self.minsize(1180, 820)
        apply_theme(self)
        self.aliquot_chains = []
        self.line_refs = []
        self.plot_points = []
        self.absolute_plot_points = []
        self.tie_points = []
        self.commence_details = {}

        body = make_scrolled_body(self)
        make_header(body, 'Schoel PLSS Deed Locator', 'Paste or import deed text to locate the tract within a section, interpret aliquot wording, show called lines and corners, and draw the tract in the section view.')

        input_sec = section(body, 'Deed Input')
        btnrow = ttk.Frame(input_sec)
        btnrow.pack(fill='x', pady=(0, 8))
        ttk.Button(btnrow, text='Import Text File', command=self.import_file, style='Primary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Parse and Draw', command=self.parse_and_draw, style='Accent.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btnrow, text='Copy Summary', command=self.copy_summary, style='Primary.TButton').pack(side='left', padx=(0, 6))
        self.input_box = text_box(input_sec, width=120, height=14)
        self.input_box.pack(fill='both', expand=True)

        summary_sec = section(body, 'Parsed Summary')
        self.summary_var = tk.StringVar(value='Paste a deed and click Parse and Draw.')
        ttk.Label(summary_sec, textvariable=self.summary_var, wraplength=1220, justify='left').pack(anchor='w')

        vis_wrap = ttk.Frame(body)
        vis_wrap.pack(fill='both', expand=True)

        left = section(vis_wrap, 'Section Location View')
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))
        right = section(vis_wrap, 'Relative Deed Plot Window')
        right.pack(side='left', fill='both', expand=True)

        self.section_canvas = tk.Canvas(left, bg='white', width=560, height=560, highlightthickness=1, highlightbackground=COLORS['line'])
        self.section_canvas.pack(fill='both', expand=True)
        self.plot_canvas = tk.Canvas(right, bg='white', width=560, height=560, highlightthickness=1, highlightbackground=COLORS['line'])
        self.plot_canvas.pack(fill='both', expand=True)

        notes = section(body, 'What This Module Reads')
        ttk.Label(notes, text=(
            'Reads Section Township Range, aliquot phrases such as SW 1/4 of NW 1/4, edge phrases such as along the north line of, '
            'quarter corners, commencement language, point of beginning, and prose metes-and-bounds calls. It resolves aliquot nesting from right to left so quarter-quarter references place in the correct quarter. '
            'When commencement ties are recognized, it draws the tract boundary inside the section view.'
        ), wraplength=1220, justify='left').pack(anchor='w')

        self.draw_section_grid()
        self.draw_plot([])

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')])
        if not path:
            return
        try:
            data = open(path, 'r', encoding='utf-8', errors='ignore').read()
            self.input_box.delete('1.0', 'end')
            self.input_box.insert('1.0', data)
        except Exception as e:
            messagebox.showerror('Import', str(e))

    def copy_summary(self):
        copy_to_clipboard(self, self.summary_var.get())
        messagebox.showinfo('Copied', 'Summary copied to clipboard.')

    def parse_and_draw(self):
        text = self.input_box.get('1.0', 'end').strip()
        if not text:
            messagebox.showwarning('PLSS Deed Locator', 'Paste deed text first.')
            return
        sec, twp, rng = find_section_info(text)
        state = find_state(text)
        self.aliquot_chains = parse_aliquot_chains(text)
        self.line_refs = parse_line_corner_refs(text)
        commencing, pob = parse_commencing_pob(text)
        self.plot_points, line_count, curve_count = compute_plot_points(text)
        self.commence_details, self.tie_points, self.absolute_plot_points = place_plot_in_section(text, self.aliquot_chains)

        plss_basis = (sec is not None or twp is not None or rng is not None or bool(self.aliquot_chains))
        lines = [
            f"State: {state or 'Not found'}",
            f"Section: {sec if sec is not None else 'Not found'}",
            f"Township: {twp or 'Not found'}",
            f"Range: {rng or 'Not found'}",
            f"Aliquot locations found: {len(self.aliquot_chains)}",
        ]
        if self.aliquot_chains:
            for i, ch in enumerate(self.aliquot_chains[:8], start=1):
                lines.append(f"  {i}. {ch['text']}")
        if self.line_refs:
            pieces = []
            for r in self.line_refs:
                if r.get('type') == 'line':
                    pieces.append(f"{r['side']} line")
                elif r.get('type') == 'quarter_corner':
                    pieces.append(f"{r.get('side', '?')} quarter corner")
                elif r.get('type') == 'corner':
                    pieces.append(f"{r.get('corner')} corner")
                else:
                    pieces.append(r.get('type', ''))
            lines.append('References found: ' + ', '.join(pieces))
        lines.append(f"Commencing found: {'Yes' if commencing else 'No'}")
        lines.append(f"Point of Beginning found: {'Yes' if pob else 'No'}")
        if self.commence_details.get('ref_chain'):
            lines.append(f"Commencement tract: {self.commence_details['ref_chain']['text']}")
        if self.commence_details.get('ref_corner'):
            lines.append(f"Commencement corner: {self.commence_details['ref_corner']}")
        if self.commence_details.get('quarter_corner'):
            lines.append(f"Commencement quarter corner: {self.commence_details['quarter_corner']}")
        lines.append(f"Relative plot line calls found: {line_count}")
        lines.append(f"Curve calls recognized: {curve_count}")
        if self.tie_points:
            lines.append(f"Commencement tie calls used before POB: {max(0, len(self.tie_points) - 1)}")
        if self.absolute_plot_points:
            lines.append(f"Section placement points drawn: {len(self.absolute_plot_points)}")
        else:
            lines.append('Section placement note: Exact tract placement inside the section view needs a recognized commencement corner or quarter-corner tie.')
        if not self.plot_points or len(self.plot_points) < 2:
            lines.append('Plot note: No plottable bearing and distance calls were recognized for the relative plot window.')
        if not plss_basis:
            lines.append('Section note: No strong PLSS section-township-range basis was found. This deed may be lot-block, subdivision, grant, Spanish land grant, metes-and-bounds only, or another non-PLSS format.')
        self.summary_var.set('\n'.join(lines))
        self.draw_section_grid()
        self.draw_plot(self.plot_points)

    def draw_section_grid(self):
        c = self.section_canvas
        c.delete('all')
        w = max(200, c.winfo_width() or 560)
        h = max(200, c.winfo_height() or 560)
        pad = 40
        size = min(w, h) - pad * 2
        x0 = (w - size) / 2
        y0 = (h - size) / 2
        x1 = x0 + size
        y1 = y0 + size

        def sx(ft):
            return x0 + (ft / SECTION_SIZE_FT) * size

        def sy(ft_north):
            return y1 - (ft_north / SECTION_SIZE_FT) * size

        c.create_rectangle(x0, y0, x1, y1, outline='black', width=2)
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        c.create_line(mx, y0, mx, y1, fill=COLORS['primary'], width=2)
        c.create_line(x0, my, x1, my, fill=COLORS['primary'], width=2)
        qxs = [x0 + size / 4, x0 + 3 * size / 4]
        qys = [y0 + size / 4, y0 + 3 * size / 4]
        for xx in qxs:
            c.create_line(xx, y0, xx, y1, fill=COLORS['line'], dash=(4, 3))
        for yy in qys:
            c.create_line(x0, yy, x1, yy, fill=COLORS['line'], dash=(4, 3))
        c.create_text((x0 + mx) / 2, (y0 + my) / 2, text='NW', font=('Segoe UI', 12, 'bold'))
        c.create_text((mx + x1) / 2, (y0 + my) / 2, text='NE', font=('Segoe UI', 12, 'bold'))
        c.create_text((x0 + mx) / 2, (my + y1) / 2, text='SW', font=('Segoe UI', 12, 'bold'))
        c.create_text((mx + x1) / 2, (my + y1) / 2, text='SE', font=('Segoe UI', 12, 'bold'))
        for x, y in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill='black')
        for x, y in [(mx, y0), (mx, y1), (x0, my), (x1, my), (mx, my)]:
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=COLORS['accent'], outline='')
        # highlighted aliquot tracts
        for idx, ch in enumerate(self.aliquot_chains):
            rx0, ry0, rx1, ry1 = ch['rect']
            X0 = x0 + rx0 * size
            Y0 = y0 + ry0 * size
            X1 = x0 + rx1 * size
            Y1 = y0 + ry1 * size
            fill = '#dce4b7' if idx == 0 else '#f8d7bf'
            c.create_rectangle(X0, Y0, X1, Y1, fill=fill, outline=COLORS['accent'], width=2, stipple='gray25')
        base_rect = rect_union([ch['rect'] for ch in self.aliquot_chains]) if self.aliquot_chains else [0, 0, 1, 1]
        bx0, by0, bx1, by1 = base_rect
        BX0 = x0 + bx0 * size
        BY0 = y0 + by0 * size
        BX1 = x0 + bx1 * size
        BY1 = y0 + by1 * size
        for ref in self.line_refs:
            if ref.get('type') == 'line':
                side = ref['side']
                if side == 'N':
                    c.create_line(BX0, BY0, BX1, BY0, fill=COLORS['accent'], width=4)
                if side == 'S':
                    c.create_line(BX0, BY1, BX1, BY1, fill=COLORS['accent'], width=4)
                if side == 'E':
                    c.create_line(BX1, BY0, BX1, BY1, fill=COLORS['accent'], width=4)
                if side == 'W':
                    c.create_line(BX0, BY0, BX0, BY1, fill=COLORS['accent'], width=4)
            elif ref.get('type') == 'quarter_corner':
                pts = {'N': (mx, y0), 'S': (mx, y1), 'E': (x1, my), 'W': (x0, my), '?': (mx, y1)}
                x, y = pts.get(ref.get('side', '?'), (mx, y1))
                c.create_oval(x - 7, y - 7, x + 7, y + 7, outline=COLORS['accent'], width=3)
            elif ref.get('type') == 'center':
                c.create_oval(mx - 7, my - 7, mx + 7, my + 7, outline=COLORS['accent'], width=3)
        # commencement tie and exact tract in section view
        if self.tie_points and len(self.tie_points) >= 2:
            tie_flat = []
            for x, y in self.tie_points:
                tie_flat.extend([sx(x), sy(y)])
            c.create_line(*tie_flat, fill=COLORS['muted'], width=2, dash=(4, 3))
            cx, cy = self.tie_points[0]
            c.create_oval(sx(cx) - 5, sy(cy) - 5, sx(cx) + 5, sy(cy) + 5, fill=COLORS['muted'], outline='')
            c.create_text(sx(cx) + 8, sy(cy) - 8, text='Commence', anchor='w', font=('Segoe UI', 8))
        if self.absolute_plot_points and len(self.absolute_plot_points) >= 2:
            tract_flat = []
            for x, y in self.absolute_plot_points:
                tract_flat.extend([sx(x), sy(y)])
            c.create_line(*tract_flat, fill=COLORS['primary_dark'], width=3)
            x_start, y_start = self.absolute_plot_points[0]
            c.create_oval(sx(x_start) - 5, sy(y_start) - 5, sx(x_start) + 5, sy(y_start) + 5, fill=COLORS['accent'], outline='')
            c.create_text(sx(x_start) + 8, sy(y_start) - 8, text='POB', anchor='w', font=('Segoe UI', 8, 'bold'))
            if len(self.absolute_plot_points) > 2 and (
                abs(self.absolute_plot_points[-1][0] - self.absolute_plot_points[0][0]) > 1e-6 or
                abs(self.absolute_plot_points[-1][1] - self.absolute_plot_points[0][1]) > 1e-6
            ):
                c.create_line(sx(self.absolute_plot_points[-1][0]), sy(self.absolute_plot_points[-1][1]), sx(self.absolute_plot_points[0][0]), sy(self.absolute_plot_points[0][1]), fill=COLORS['accent'], dash=(5, 3), width=2)
        c.create_text(w / 2, 18, text='Section View with quarter lines, quarter-quarter lines, corners, and tract placement', font=('Segoe UI', 10, 'bold'), fill=COLORS['text'])

    def draw_plot(self, pts):
        c = self.plot_canvas
        c.delete('all')
        w = max(200, c.winfo_width() or 560)
        h = max(200, c.winfo_height() or 560)
        pad = 40
        c.create_text(w / 2, 18, text='Relative Deed Plot Window', font=('Segoe UI', 10, 'bold'), fill=COLORS['text'])
        if not pts or len(pts) < 2:
            c.create_text(w / 2, h / 2, text='No bearing and distance calls recognized for plotting.', font=('Segoe UI', 12), fill=COLORS['muted'])
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
            c.create_text(X + 8, Y - 8, text=str(i + 1), anchor='w', font=('Segoe UI', 8))
        c.create_line(w - 30, h - 60, w - 30, h - 100, arrow='last', width=2)
        c.create_text(w - 30, h - 110, text='N', font=('Segoe UI', 10, 'bold'))
        if len(pts) > 2 and (abs(pts[-1][0] - pts[0][0]) > 1e-6 or abs(pts[-1][1] - pts[0][1]) > 1e-6):
            c.create_line(tx(pts[-1][0]), ty(pts[-1][1]), tx(pts[0][0]), ty(pts[0][1]), dash=(5, 3), fill=COLORS['accent'], width=2)


def run():
    App().mainloop()


def main():
    run()

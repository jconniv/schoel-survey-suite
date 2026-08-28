import os
import re
import sys
import math
import tkinter as tk
from tkinter import ttk

from ui_common import apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard

TITLE = 'AI Closure Assistant'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PLOTTER_ANGLE_DIR = os.path.join(BASE_DIR, 'plotter_angle')
if PLOTTER_ANGLE_DIR not in sys.path:
    sys.path.insert(0, PLOTTER_ANGLE_DIR)

try:
    from parser_deed import parse_deed_to_steps, parse_start_bearing
    from traverse import solve_traverse
except Exception:
    parse_deed_to_steps = None
    parse_start_bearing = None
    solve_traverse = None

OCR_HINTS = [
    ('º', '°'),
    ('’', "'"),
    ('‘', "'"),
    ('“', '"'),
    ('”', '"'),
    ('\\u00a0', ' '),
]


def normalize_text(text: str) -> str:
    out = text
    for a, b in OCR_HINTS:
        out = out.replace(a, b)
    out = out.replace('\r\n', '\n').replace('\r', '\n')
    out = re.sub(r'[ \t]+', ' ', out)
    return out.strip()


def split_calls(text: str):
    cleaned = normalize_text(text)
    parts = re.split(r'\bTHENCE\b|;|\n', cleaned, flags=re.IGNORECASE)
    return [p.strip(' ,.') for p in parts if p.strip(' ,.\n\t')]


def fmt(v: float) -> str:
    return f'{v:,.4f}'


def analyze_text(text: str, start_bearing: str = '') -> str:
    raw = text.strip()
    if not raw:
        return 'Paste deed text first.'

    lines = []
    cleaned = normalize_text(raw)
    calls = split_calls(cleaned)
    lower = cleaned.lower()

    lines.append('AI Closure Assistant review')
    lines.append('')
    lines.append(f'Text length: {len(cleaned):,} characters')
    lines.append(f'Possible call fragments found: {len(calls)}')
    lines.append('')

    findings = []
    suspicious = []

    if 'thence' not in lower:
        findings.append('No THENCE wording was found. The deed may still be valid, but line separation may need manual cleanup.')
    if cleaned.count('°') == 0 and any(w in lower for w in ['north', 'south', 'east', 'west', ' n ', ' s ', ' e ', ' w ']):
        findings.append('Directional wording was found but no degree symbol was found. The parser may need cleaned bearing formatting.')
    if 'curve' in lower and 'radius' not in lower:
        findings.append('Curve wording appears present but no RADIUS term was found.')
    if any(ch in raw for ch in ['º', '’', '‘', '“', '”']):
        findings.append('Smart quotes or alternate symbols were found. These can cause parsing problems in some deed plotters.')

    bearing_like = re.compile(r'\b[NS]\b.*?\b[EW]\b', re.IGNORECASE)
    distance_like = re.compile(r'(?:distance\s+of|a\s+distance\s+of|for a distance of|)\s*\d+(?:\.\d+)?\s*(?:feet|foot|ft\.?|\'|f\b)', re.IGNORECASE)

    for idx, call in enumerate(calls, start=1):
        call_findings = []
        up = call.upper()

        if ('NORTH' in up or 'SOUTH' in up or re.search(r'\b[NS]\b', up)) and not ('EAST' in up or 'WEST' in up or re.search(r'\b[EW]\b', up)):
            call_findings.append('has a north/south direction but no east/west quadrant')
        if ('EAST' in up or 'WEST' in up or re.search(r'\b[EW]\b', up)) and not ('NORTH' in up or 'SOUTH' in up or re.search(r'\b[NS]\b', up)):
            call_findings.append('has an east/west direction but no north/south quadrant')
        if ('CURVE' not in up and 'ARC' not in up) and not distance_like.search(call):
            call_findings.append('does not appear to contain a clear distance')
        nums = re.findall(r'\d+(?:\.\d+)?', call)
        if len(nums) >= 2 and not re.search(r"(?:FEET|FOOT|FT\.?|')", up) and 'CURVE' not in up:
            call_findings.append('has numbers but no clear feet marker, which may make paste parsing fail')
        if re.search(r'\b[SO]\b', up) and ' 0' in up:
            pass
        if re.search(r'\b5\b', up) and ('RIGHT' in up or 'LEFT' in up):
            call_findings.append('may contain an OCR issue between S and 5')
        if call.count('"') == 1:
            call_findings.append('has an unmatched seconds quote')
        if call_findings:
            suspicious.append((idx, call, call_findings))

    lines.append('General findings')
    if findings:
        for item in findings:
            lines.append(f'- {item}')
    else:
        lines.append('- No broad formatting issues were flagged by the local review rules.')
    lines.append('')

    lines.append('Suspicious calls')
    if suspicious:
        for idx, call, call_findings in suspicious[:12]:
            lines.append(f'- Call {idx}: {call}')
            for item in call_findings:
                lines.append(f'    • {item}')
    else:
        lines.append('- No obviously suspicious calls were flagged by the local review rules.')
    lines.append('')

    # Try an interior-angle parse and closure solve when plotter modules are available.
    lines.append('Local closure test')
    if parse_deed_to_steps and parse_start_bearing and solve_traverse:
        bearing_text = (start_bearing or '').strip() or '270'
        try:
            steps, log = parse_deed_to_steps(cleaned)
            az = parse_start_bearing(bearing_text)
            solved = solve_traverse(az, steps)
            lines.append(f'- Parsed steps: {len(steps)}')
            summary = solved.get('summary', '').strip().splitlines()
            for s in summary[1:]:
                lines.append(f'- {s}')
            misclosure = None
            m = re.search(r'Linear misclosure\s+([0-9.,]+)', solved.get('summary', ''))
            if m:
                misclosure = float(m.group(1).replace(',', ''))
            if misclosure is not None:
                if misclosure <= 0.05:
                    lines.append('- This interior-angle style parse closes very well under the local solver.')
                elif misclosure <= 1.0:
                    lines.append('- This interior-angle style parse nearly closes. A small typo or formatting issue may be the cause.')
                else:
                    lines.append('- This interior-angle style parse does not close well. Review the suspicious calls listed above.')
            lines.append('')
            lines.append('Parse log excerpt')
            for s in log.splitlines()[:14]:
                lines.append(f'- {s}')
        except Exception as e:
            lines.append(f'- The local interior-angle parser could not solve this text: {e}')
            lines.append('- That usually means the deed language needs cleanup, or it is primarily a bearing-style deed rather than an interior-angle style deed.')
    else:
        lines.append('- Local closure test is unavailable because the interior-angle plotter parser was not found.')
    lines.append('')

    lines.append('Suggested next checks')
    lines.append('- Compare the pasted deed to the source PDF or Word file and look for OCR issues in quadrants, degree symbols, and distances, including feet written as foot, feet, ft, or apostrophe marks.')
    lines.append('- Check any call that has a direction pair missing or a distance missing.')
    lines.append('- If the deed should close, review whether one quadrant is flipped or one distance lost a digit during paste.')
    lines.append('- Keep the original deed text unchanged and test one possible fix at a time.')
    lines.append('')
    lines.append('This assistant is local and rule-based. It suggests likely problem spots but does not rewrite or certify your deed.')
    return '\n'.join(lines)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry('1100x860')
        apply_theme(self)

        body = make_scrolled_body(self)
        make_header(
            body,
            TITLE,
            'Paste a deed here to flag likely bad calls, formatting problems, and possible reasons a tract does not close. This keeps your legal wording intact and only suggests likely trouble spots.'
        )

        input_sec = section(body, 'Deed Text')
        self.input_box = text_box(input_sec, height=18)
        self.input_box.pack(fill='both', expand=True)

        control_row = ttk.Frame(input_sec)
        control_row.pack(fill='x', pady=(8, 0))
        ttk.Label(control_row, text='Starting bearing or azimuth for local interior-angle closure test').pack(side='left')
        self.start_entry = ttk.Entry(control_row, width=28)
        self.start_entry.insert(0, '270')
        self.start_entry.pack(side='left', padx=(10, 0))

        btn_row = ttk.Frame(input_sec)
        btn_row.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_row, text='Analyze Deed', style='Primary.TButton', command=self.run_analysis).pack(side='left')
        ttk.Button(btn_row, text='Clear', style='Accent.TButton', command=self.clear_all).pack(side='left', padx=(8, 0))

        out_sec = section(body, 'Findings')
        self.output_box = text_box(out_sec, height=24)
        self.output_box.pack(fill='both', expand=True)
        ttk.Button(out_sec, text='Copy Findings', style='Accent.TButton', command=lambda: copy_to_clipboard(self, self.output_box.get('1.0', 'end').strip())).pack(anchor='w', pady=(8, 0))

    def run_analysis(self):
        result = analyze_text(self.input_box.get('1.0', 'end'), self.start_entry.get())
        set_output(self.output_box, result)

    def clear_all(self):
        self.input_box.delete('1.0', 'end')
        self.output_box.delete('1.0', 'end')
        self.start_entry.delete(0, 'end')
        self.start_entry.insert(0, '270')


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()

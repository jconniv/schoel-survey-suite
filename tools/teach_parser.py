import json
import os
import re
import unicodedata
import tkinter as tk
from tkinter import ttk, messagebox

from ui_common import (
    build_title,
    apply_theme,
    make_scrolled_body,
    make_header,
    section,
    text_box,
    set_output,
    copy_to_clipboard,
)

TITLE = 'Teach Parser'
APP_DIR_NAME = 'SchoelSurveySuite'
MEMORY_FILE_NAME = 'parser_memory.json'

NORMALIZE_REPLACEMENTS = [
    ('º', '°'),
    ('’', "'"),
    ('‘', "'"),
    ('“', '"'),
    ('”', '"'),
    ('\u00a0', ' '),
]

COMMON_OCR_REPLACEMENTS = [
    (' Hne ', ' line '),
    (' hne ', ' line '),
    (' ffne ', ' line '),
    (' tho ', ' the '),
    (' RaUroad ', ' Railroad '),
    (' comer ', ' corner '),
    (' lo the ', ' to the '),
    (' lo ', ' to '),
]


def app_data_dir() -> str:
    root = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    path = os.path.join(root, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def memory_path() -> str:
    return os.path.join(app_data_dir(), MEMORY_FILE_NAME)


def load_memory() -> dict:
    path = memory_path()
    if not os.path.exists(path):
        return {'line_corrections': [], 'phrase_replacements': []}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.setdefault('line_corrections', [])
        data.setdefault('phrase_replacements', [])
        return data
    except Exception:
        return {'line_corrections': [], 'phrase_replacements': []}


def save_memory(data: dict) -> None:
    with open(memory_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _strip_accents(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def normalize_text(text: str) -> str:
    out = text.replace('\r\n', '\n').replace('\r', '\n')
    out = _strip_accents(out)
    for a, b in NORMALIZE_REPLACEMENTS:
        out = out.replace(a, b)
    for a, b in COMMON_OCR_REPLACEMENTS:
        out = out.replace(a, b)
    out = re.sub(r'(?i)\bfeet\b', "'", out)
    out = re.sub(r'(?i)\bfoot\b', "'", out)
    out = re.sub(r'(?i)\bft\.?\b', "'", out)
    out = re.sub(r"(?<=\d)\s+'\b", "'", out)
    out = re.sub(r'(?i)\bdegrees?\b', '°', out)
    out = re.sub(r"(?i)\bminutes?\b", "'", out)
    out = re.sub(r'(?i)\bseconds?\b', '"', out)
    out = re.sub(
        r'(?<![;:.])\n(?!\s*(?:THENCE|BEGIN|COMMENCE|LESS AND EXCEPT|SUBJECT TO)\b)',
        ' ',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r'\s*;\s*', '; ', out)
    out = re.sub(r'[ \t]+', ' ', out)
    out = re.sub(r' *\n *', '\n', out)
    return out.strip()


def split_calls(text: str):
    cleaned = normalize_text(text)
    parts = re.split(r'\bTHENCE\b|;|\n', cleaned, flags=re.IGNORECASE)
    return [p.strip(' ,.\t') for p in parts if p.strip(' ,.\n\t')]


def apply_memory(text: str, memory: dict):
    out = text
    applied = []
    for item in memory.get('phrase_replacements', []):
        src = item.get('from', '')
        dst = item.get('to', '')
        if src and src in out:
            out = out.replace(src, dst)
            applied.append(f"phrase: {src} -> {dst}")
    lines = out.splitlines()
    corrected = []
    line_map = {
        item.get('original', '').strip(): item.get('corrected', '').strip()
        for item in memory.get('line_corrections', [])
        if item.get('original') and item.get('corrected')
    }
    for line in lines:
        stripped = line.strip()
        corrected.append(line_map.get(stripped, line))
        if stripped in line_map:
            applied.append(f"line: {stripped}")
    return '\n'.join(corrected), applied


def analyze_line(line: str, mode: str = 'general'):
    issues = []
    up = line.upper()
    if not line.strip():
        return issues
    has_distance = bool(re.search(r"\d+(?:\.\d+)?\s*(?:'|FEET|FOOT|FT\b)", up, re.IGNORECASE))
    if not has_distance and 'CURVE' not in up and 'ARC' not in up:
        issues.append('no clear distance found')
    if any(w in up for w in ['NORTH', 'SOUTH', 'EAST', 'WEST']) or re.search(r'\b[NS]\b', up):
        if not (('EAST' in up or 'WEST' in up) or re.search(r'\b[EW]\b', up)):
            issues.append('direction wording may be incomplete')
    if line.count('"') == 1:
        issues.append('unmatched seconds quote')
    if re.search(r"\d+\.\d+\s*(?:FEET|FOOT|FT\b)", up) and "'" not in line:
        issues.append('distance uses word form and may need normalization for some parsers')
    if mode == 'interior_angle':
        if 'LEFT' not in up and 'RIGHT' not in up and 'CURVE' not in up and 'ARC' not in up:
            issues.append('interior-angle text may need LEFT or RIGHT turn wording')
    if mode == 'bearing':
        if not ((('N' in up) or ('NORTH' in up) or ('S' in up) or ('SOUTH' in up)) and (('E' in up) or ('EAST' in up) or ('W' in up) or ('WEST' in up))):
            issues.append('bearing-style line may be missing a full quadrant')
    return issues


def build_report(original_text: str, working_text: str, mode: str, applied):
    lines = []
    lines.append('Teach Parser review')
    lines.append('')
    lines.append(f'Mode: {mode}')
    calls = split_calls(working_text)
    lines.append(f'Call fragments found: {len(calls)}')
    lines.append('')
    if applied:
        lines.append('Applied learned patterns')
        for item in applied[:20]:
            lines.append(f'- {item}')
        lines.append('')
    lines.append('Line review')
    any_issue = False
    for idx, line in enumerate(calls, start=1):
        issues = analyze_line(line, mode)
        if issues:
            any_issue = True
            lines.append(f'- Call {idx}: {line}')
            for issue in issues:
                lines.append(f'    • {issue}')
    if not any_issue:
        lines.append('- No obvious formatting issues were flagged by the local parser trainer rules.')
    lines.append('')
    lines.append('Normalized deed preview')
    lines.append(working_text.strip() or '[empty]')
    return '\n'.join(lines)


def _add_entry_paste_support(widget: ttk.Entry):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label='Cut', command=lambda: widget.event_generate('<<Cut>>'))
    menu.add_command(label='Copy', command=lambda: widget.event_generate('<<Copy>>'))
    menu.add_command(label='Paste', command=lambda: widget.event_generate('<<Paste>>'))
    widget.bind('<Control-v>', lambda e: (widget.event_generate('<<Paste>>'), 'break'))
    widget.bind('<Control-V>', lambda e: (widget.event_generate('<<Paste>>'), 'break'))
    widget.bind('<Control-c>', lambda e: (widget.event_generate('<<Copy>>'), 'break'))
    widget.bind('<Control-x>', lambda e: (widget.event_generate('<<Cut>>'), 'break'))
    widget.bind('<Button-3>', lambda e: (menu.tk_popup(e.x_root, e.y_root), 'break'))


class TeachParserWindow:
    def __init__(self, root: tk.Misc, seed_text: str = '', mode: str = 'general'):
        self.root = root
        self.mode = mode
        self.memory = load_memory()
        self._build(seed_text)

    def _build(self, seed_text: str):
        apply_theme(self.root)
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.geometry('1180x900')
        body = make_scrolled_body(self.root) if isinstance(self.root, tk.Tk) else ttk.Frame(self.root)
        if not isinstance(self.root, tk.Tk):
            body.pack(fill='both', expand=True)

        make_header(body, TITLE, 'Teach the parser how to clean deed text, remember approved fixes, and reuse them the next time a deed is worded a little off.')

        controls = section(body, 'Parser Training Controls')
        row = ttk.Frame(controls)
        row.pack(fill='x')
        ttk.Label(row, text='Mode').pack(side='left')
        self.mode_var = tk.StringVar(value=self.mode)
        mode_box = ttk.Combobox(row, textvariable=self.mode_var, values=['general', 'bearing', 'interior_angle'], width=18, state='readonly')
        mode_box.pack(side='left', padx=(8, 16))
        ttk.Button(row, text='Normalize Text', style='Primary.TButton', command=self.normalize_current).pack(side='left')
        ttk.Button(row, text='Apply Learned Patterns', style='Primary.TButton', command=self.apply_learned).pack(side='left', padx=(8, 0))
        ttk.Button(row, text='Analyze', style='Primary.TButton', command=self.analyze).pack(side='left', padx=(8, 0))
        ttk.Button(row, text='Copy Cleaned Text', style='Accent.TButton', command=self.copy_cleaned).pack(side='left', padx=(8, 0))

        deed_sec = section(body, 'Original Deed Text')
        self.original_box = text_box(deed_sec, height=14)
        self.original_box.pack(fill='both', expand=True)
        if seed_text:
            self.original_box.insert('1.0', seed_text)

        cleaned_sec = section(body, 'Cleaned Deed Text for Plotter Paste')
        self.cleaned_box = text_box(cleaned_sec, height=14)
        self.cleaned_box.pack(fill='both', expand=True)

        learn_sec = section(body, 'Teach This Correction')
        ttk.Label(learn_sec, text='Use this when the parser did not understand a deed line correctly. Save your approved fix and the suite will remember it.').pack(anchor='w', pady=(0, 8))
        grid = ttk.Frame(learn_sec)
        grid.pack(fill='x')
        ttk.Label(grid, text='Original line').grid(row=0, column=0, sticky='w')
        ttk.Label(grid, text='Corrected line').grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.orig_line = ttk.Entry(grid)
        self.orig_line.grid(row=0, column=1, sticky='ew', padx=(8, 0))
        ttk.Button(grid, text='Paste', style='Accent.TButton', command=lambda: self.orig_line.event_generate('<<Paste>>')).grid(row=0, column=2, padx=(8, 0))
        self.corr_line = ttk.Entry(grid)
        self.corr_line.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(6, 0))
        ttk.Button(grid, text='Paste', style='Accent.TButton', command=lambda: self.corr_line.event_generate('<<Paste>>')).grid(row=1, column=2, padx=(8, 0), pady=(6, 0))
        _add_entry_paste_support(self.orig_line)
        _add_entry_paste_support(self.corr_line)
        grid.columnconfigure(1, weight=1)
        btn_row = ttk.Frame(learn_sec)
        btn_row.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_row, text='Save Exact Line Correction', style='Primary.TButton', command=self.save_line_correction).pack(side='left')
        ttk.Button(btn_row, text='Save Phrase Replacement', style='Accent.TButton', command=self.save_phrase_replacement).pack(side='left', padx=(8, 0))
        ttk.Button(btn_row, text='Show Memory File', style='Accent.TButton', command=self.show_memory_path).pack(side='left', padx=(8, 0))

        findings = section(body, 'Findings')
        self.output_box = text_box(findings, height=18)
        self.output_box.pack(fill='both', expand=True)
        ttk.Button(findings, text='Copy Findings', style='Accent.TButton', command=lambda: copy_to_clipboard(self.root, self.output_box.get('1.0', 'end').strip())).pack(anchor='w', pady=(8, 0))

        self.normalize_current()
        self.analyze()

    def current_mode(self) -> str:
        return (self.mode_var.get() or 'general').strip()

    def normalize_current(self):
        raw = self.original_box.get('1.0', 'end').strip()
        cleaned = normalize_text(raw)
        set_output(self.cleaned_box, cleaned)

    def apply_learned(self):
        raw = self.original_box.get('1.0', 'end').strip()
        cleaned = normalize_text(raw)
        updated, applied = apply_memory(cleaned, self.memory)
        set_output(self.cleaned_box, updated)
        msg = 'Applied learned patterns.\n\n' + ('\n'.join(applied[:20]) if applied else 'No saved patterns matched this deed.')
        messagebox.showinfo(TITLE, msg)
        self.analyze()

    def analyze(self):
        mode = self.current_mode()
        cleaned = self.cleaned_box.get('1.0', 'end').strip() or normalize_text(self.original_box.get('1.0', 'end').strip())
        _, applied = apply_memory(cleaned, self.memory)
        report = build_report(self.original_box.get('1.0', 'end').strip(), cleaned, mode, applied)
        set_output(self.output_box, report)

    def copy_cleaned(self):
        copy_to_clipboard(self.root, self.cleaned_box.get('1.0', 'end').strip())
        messagebox.showinfo(TITLE, 'Cleaned deed text copied to clipboard.')

    def save_line_correction(self):
        original = self.orig_line.get().strip()
        corrected = self.corr_line.get().strip()
        if not original or not corrected:
            messagebox.showwarning(TITLE, 'Enter both the original line and the corrected line first.')
            return
        self.memory = load_memory()
        self.memory.setdefault('line_corrections', [])
        self.memory['line_corrections'].append({'original': original, 'corrected': corrected, 'mode': self.current_mode()})
        save_memory(self.memory)
        messagebox.showinfo(TITLE, 'Exact line correction saved.')
        self.orig_line.delete(0, 'end')
        self.corr_line.delete(0, 'end')

    def save_phrase_replacement(self):
        original = self.orig_line.get().strip()
        corrected = self.corr_line.get().strip()
        if not original or not corrected:
            messagebox.showwarning(TITLE, 'Enter both the original phrase and the replacement first.')
            return
        self.memory = load_memory()
        self.memory.setdefault('phrase_replacements', [])
        self.memory['phrase_replacements'].append({'from': original, 'to': corrected, 'mode': self.current_mode()})
        save_memory(self.memory)
        messagebox.showinfo(TITLE, 'Phrase replacement saved.')
        self.orig_line.delete(0, 'end')
        self.corr_line.delete(0, 'end')

    def show_memory_path(self):
        messagebox.showinfo(TITLE, f'Parser memory file\n\n{memory_path()}')


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title(TITLE))
        TeachParserWindow(self)


def launch(parent=None, seed_text: str = '', mode: str = 'general'):
    if parent is None:
        app = App()
        if seed_text:
            app.destroy()
            app = tk.Tk()
            app.title(build_title(TITLE))
            win = TeachParserWindow(app, seed_text=seed_text, mode=mode)
            app.mainloop()
            return win
        app.mainloop()
        return app
    win = tk.Toplevel(parent)
    win.title(build_title(TITLE))
    return TeachParserWindow(win, seed_text=seed_text, mode=mode)


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()

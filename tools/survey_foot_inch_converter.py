from fractions import Fraction
import re
import tkinter as tk
from tkinter import ttk, messagebox

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, set_output

TITLE = 'Survey Foot and Inch Converter'


def format_inches_from_feet(value_ft: float, denom: int) -> str:
    inches = value_ft * 12.0
    sign = '-' if inches < 0 else ''
    abs_inches = abs(inches)
    whole_inches = int(abs_inches)
    frac = abs_inches - whole_inches
    frac_fraction = Fraction(frac).limit_denominator(denom)
    if frac_fraction.numerator == frac_fraction.denominator:
        whole_inches += 1
        frac_fraction = Fraction(0, 1)

    dec_in = f'{inches:.6f}'
    dec_ft = f'{value_ft:.6f}'

    if frac_fraction.numerator == 0:
        mixed = f'{sign}{whole_inches}"'
    elif whole_inches == 0:
        mixed = f'{sign}{frac_fraction.numerator}/{frac_fraction.denominator}"'
    else:
        mixed = f'{sign}{whole_inches}" {frac_fraction.numerator}/{frac_fraction.denominator}"'

    return (
        f'Decimal survey feet: {dec_ft}\n'
        f'Decimal inches: {dec_in}\n'
        f'Rounded inch fraction: {mixed}'
    )


INCH_PATTERN = re.compile(
    r'''^\s*
    (?P<sign>-)?\s*
    (?:(?P<whole>\d+(?:\.\d+)?)\s*(?:in|inch|inches|"|')?)?\s*
    (?:(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*(?:in|inch|inches|")?)?\s*$''',
    re.IGNORECASE | re.VERBOSE,
)


def parse_inches(text: str) -> float:
    s = text.strip().lower()
    if not s:
        raise ValueError('Enter an inch value first.')

    s = s.replace('”', '"').replace('“', '"').replace("''", '"')
    s = s.replace(' and ', ' ')
    s = s.replace('-', ' -') if s.startswith('-') else s

    m = INCH_PATTERN.match(s)
    if not m:
        raise ValueError(
            'Use an inch format like 4" 1/2", 4 1/2, 4.5, 1/2", or 7".'
        )

    sign = -1.0 if m.group('sign') else 1.0
    whole = float(m.group('whole')) if m.group('whole') else 0.0
    frac = 0.0
    if m.group('num') and m.group('den'):
        den = int(m.group('den'))
        if den == 0:
            raise ValueError('Fraction denominator cannot be zero.')
        frac = int(m.group('num')) / den

    if whole == 0.0 and frac == 0.0:
        raise ValueError('Enter a valid inch value.')

    return sign * (whole + frac)


def format_feet_from_inches(value_in: float) -> str:
    feet = value_in / 12.0
    return (
        f'Decimal inches: {value_in:.6f}\n'
        f'Decimal survey feet: {feet:.6f}'
    )


def convert_feet_to_inches(feet_var, denom_var, out):
    raw = feet_var.get().strip()
    if not raw:
        messagebox.showwarning(TITLE, 'Enter a decimal survey foot value first.')
        return
    try:
        val = float(raw)
    except ValueError:
        messagebox.showerror(TITLE, 'Enter a valid decimal survey foot value.')
        return
    set_output(out, format_inches_from_feet(val, int(denom_var.get())))



def convert_inches_to_feet(inches_var, out):
    raw = inches_var.get().strip()
    if not raw:
        messagebox.showwarning(TITLE, 'Enter an inch value first.')
        return
    try:
        val = parse_inches(raw)
    except ValueError as e:
        messagebox.showerror(TITLE, str(e))
        return
    set_output(out, format_feet_from_inches(val))



def convert_bulk_feet(inp, denom_var, out):
    rows = []
    for line in inp.get('1.0', 'end').splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            val = float(s)
            rows.append(f'{s} ft | ' + format_inches_from_feet(val, int(denom_var.get())).replace('\n', ' | '))
        except ValueError:
            rows.append(f'{s} | invalid decimal survey foot value')
    set_output(out, '\n'.join(rows) if rows else 'Paste one decimal survey foot value per line, then click Convert Feet List.')



def convert_bulk_inches(inp, out):
    rows = []
    for line in inp.get('1.0', 'end').splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            val = parse_inches(s)
            rows.append(f'{s} | ' + format_feet_from_inches(val).replace('\n', ' | '))
        except ValueError as e:
            rows.append(f'{s} | {e}')
    set_output(out, '\n'.join(rows) if rows else 'Paste one inch value per line, then click Convert Inch List.')



def main():
    root = tk.Tk()
    root.title(build_title(TITLE))
    root.geometry('960x920')
    apply_theme(root)
    body = make_scrolled_body(root)
    make_header(body, TITLE, 'Convert decimal survey feet to inches and rounded fractions, or convert inch fractions like 4" 1/2" back to decimal survey feet.')

    top = section(body, 'Survey Feet to Inches')
    row = ttk.Frame(top)
    row.pack(fill='x', pady=(0, 8))
    ttk.Label(row, text='Survey feet').grid(row=0, column=0, sticky='w', padx=(0, 8))
    feet_var = tk.StringVar()
    ttk.Entry(row, textvariable=feet_var, width=22).grid(row=0, column=1, sticky='w')
    ttk.Label(row, text='Round fraction to').grid(row=0, column=2, sticky='w', padx=(16, 8))
    denom_var = tk.StringVar(value='16')
    ttk.Combobox(row, textvariable=denom_var, state='readonly', values=['2', '4', '8', '16', '32', '64'], width=8).grid(row=0, column=3, sticky='w')
    out_ft = text_box(top, height=6)
    out_ft.pack(fill='both', expand=True)
    ttk.Button(top, text='Convert Survey Feet', style='Primary.TButton', command=lambda: convert_feet_to_inches(feet_var, denom_var, out_ft)).pack(anchor='w', pady=(8, 0))

    mid = section(body, 'Inches and Fractions to Survey Feet')
    ttk.Label(mid, text='Accepted examples: 4" 1/2", 4 1/2, 4.5, 1/2", 7"').pack(anchor='w', pady=(0, 6))
    inch_row = ttk.Frame(mid)
    inch_row.pack(fill='x', pady=(0, 8))
    ttk.Label(inch_row, text='Inches').grid(row=0, column=0, sticky='w', padx=(0, 8))
    inches_var = tk.StringVar()
    ttk.Entry(inch_row, textvariable=inches_var, width=22).grid(row=0, column=1, sticky='w')
    out_in = text_box(mid, height=5)
    out_in.pack(fill='both', expand=True)
    ttk.Button(mid, text='Convert Inches', style='Accent.TButton', command=lambda: convert_inches_to_feet(inches_var, out_in)).pack(anchor='w', pady=(8, 0))

    bulk_feet = section(body, 'Bulk Survey Feet List')
    ttk.Label(bulk_feet, text='Paste one decimal survey foot value per line.').pack(anchor='w', pady=(0, 6))
    feet_inp = text_box(bulk_feet, height=10)
    feet_inp.pack(fill='both', expand=True)
    feet_list_out = text_box(bulk_feet, height=12)
    feet_list_out.pack(fill='both', expand=True, pady=(8, 0))
    ttk.Button(bulk_feet, text='Convert Feet List', style='Primary.TButton', command=lambda: convert_bulk_feet(feet_inp, denom_var, feet_list_out)).pack(anchor='w', pady=(8, 0))

    bulk_inches = section(body, 'Bulk Inch List')
    ttk.Label(bulk_inches, text='Paste one inch value per line using forms like 4" 1/2" or 7".').pack(anchor='w', pady=(0, 6))
    inch_inp = text_box(bulk_inches, height=10)
    inch_inp.pack(fill='both', expand=True)
    inch_list_out = text_box(bulk_inches, height=12)
    inch_list_out.pack(fill='both', expand=True, pady=(8, 0))
    ttk.Button(bulk_inches, text='Convert Inch List', style='Accent.TButton', command=lambda: convert_bulk_inches(inch_inp, inch_list_out)).pack(anchor='w', pady=(8, 0))

    root.mainloop()


if __name__ == '__main__':
    main()

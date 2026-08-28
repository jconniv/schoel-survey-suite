import math
import tkinter as tk
from tkinter import ttk, messagebox

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard

TITLE = 'Curve Table Generator'


def compute(radius, delta_deg, arc, chord):
    vals = {'radius': radius, 'delta': delta_deg, 'arc': arc, 'chord': chord}
    filled = {k: v for k, v in vals.items() if v not in (None, '')}
    if len(filled) < 2:
        raise ValueError('Enter at least two values.')

    r = float(radius) if radius not in (None, '') else None
    d = float(delta_deg) if delta_deg not in (None, '') else None
    a = float(arc) if arc not in (None, '') else None
    c = float(chord) if chord not in (None, '') else None

    if r is not None and d is not None:
        a = math.radians(d) * r
        c = 2 * r * math.sin(math.radians(d) / 2)
    elif r is not None and a is not None:
        d = math.degrees(a / r)
        c = 2 * r * math.sin(math.radians(d) / 2)
    elif r is not None and c is not None:
        d = math.degrees(2 * math.asin(c / (2 * r)))
        a = math.radians(d) * r
    elif d is not None and c is not None:
        r = c / (2 * math.sin(math.radians(d) / 2))
        a = math.radians(d) * r
    elif d is not None and a is not None:
        r = a / math.radians(d)
        c = 2 * r * math.sin(math.radians(d) / 2)
    elif a is not None and c is not None:
        # iterative solve for delta
        lo, hi = 1e-9, math.pi - 1e-9
        for _ in range(100):
            mid = (lo + hi) / 2
            ratio = mid / (2 * math.sin(mid / 2))
            target = a / c
            if ratio < target:
                lo = mid
            else:
                hi = mid
        rad = (lo + hi) / 2
        d = math.degrees(rad)
        r = a / rad
    tangent = r * math.tan(math.radians(d) / 2)
    ext = r * (1 / math.cos(math.radians(d) / 2) - 1)
    mid = r * (1 - math.cos(math.radians(d) / 2))
    return r, d, a, c, tangent, ext, mid


def main():
    root = tk.Tk()
    root.title(build_title(TITLE))
    root.geometry('900x680')
    apply_theme(root)
    body = make_scrolled_body(root)
    make_header(body, TITLE, 'Enter any two curve values and the suite will solve the rest.')

    frm = section(body, 'Inputs')
    entries = {}
    for i, lbl in enumerate(['Radius', 'Delta Angle Degrees', 'Arc Length', 'Chord Length']):
        ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky='w', padx=(0, 10), pady=6)
        ent = ttk.Entry(frm, width=22)
        ent.grid(row=i, column=1, sticky='w', pady=6)
        entries[lbl] = ent

    out_sec = section(body, 'Curve Output')
    out = text_box(out_sec, height=14)
    out.pack(fill='both', expand=True)

    def solve():
        try:
            r, d, a, c, t, e, m = compute(entries['Radius'].get(), entries['Delta Angle Degrees'].get(), entries['Arc Length'].get(), entries['Chord Length'].get())
            txt = (
                f'Radius: {r:,.4f}\n'
                f'Delta Angle: {d:,.6f} degrees\n'
                f'Arc Length: {a:,.4f}\n'
                f'Chord Length: {c:,.4f}\n'
                f'Tangent: {t:,.4f}\n'
                f'External: {e:,.4f}\n'
                f'Middle Ordinate: {m:,.4f}\n'
            )
            set_output(out, txt)
        except Exception as exc:
            messagebox.showerror(TITLE, str(exc))

    btns = ttk.Frame(frm)
    btns.grid(row=5, column=0, columnspan=2, sticky='w', pady=(8, 0))
    ttk.Button(btns, text='Solve Curve', style='Primary.TButton', command=solve).pack(side='left')
    ttk.Button(btns, text='Copy Output', style='Accent.TButton', command=lambda: copy_to_clipboard(root, out.get('1.0', 'end').strip())).pack(side='left', padx=6)
    root.mainloop()


if __name__ == '__main__':
    main()

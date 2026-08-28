import tkinter as tk
from tkinter import ttk

from ui_common import apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard

TITLE = 'Map Check Assistant'

CHECKS = [
    'North arrow shown',
    'Scale shown',
    'Basis of bearing note added',
    'Vertical datum note added',
    'Units note added',
    'Boundary note added or not boundary note added',
    'Control points labeled',
    'Property lines labeled',
    'Image source and flight date noted',
    'Legend added if needed',
    'Title block complete',
    'Sheet notes checked',
]


def main():
    root = tk.Tk()
    root.title(TITLE)
    root.geometry('980x760')
    apply_theme(root)
    body = make_scrolled_body(root)
    make_header(body, TITLE, 'Use this as a quick pre-issue and QA review checklist for exhibits, control sheets, and mapping deliverables.')

    frm = section(body, 'Checklist')
    vars_ = []
    for item in CHECKS:
        var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text=item, variable=var).pack(anchor='w', pady=2)
        vars_.append((item, var))

    out_sec = section(body, 'Review Summary')
    out = text_box(out_sec, height=18)
    out.pack(fill='both', expand=True)

    def build():
        complete = [item for item, var in vars_ if var.get()]
        remaining = [item for item, var in vars_ if not var.get()]
        txt = 'Map Check Summary\n\nCompleted\n' + '\n'.join(f'- {x}' for x in complete)
        txt += '\n\nStill to review\n' + '\n'.join(f'- {x}' for x in remaining)
        set_output(out, txt)

    ttk.Button(frm, text='Build Summary', style='Primary.TButton', command=build).pack(anchor='w', pady=(8, 0))
    ttk.Button(out_sec, text='Copy Summary', style='Accent.TButton', command=lambda: copy_to_clipboard(root, out.get('1.0', 'end').strip())).pack(anchor='w', pady=(8, 0))
    root.mainloop()


if __name__ == '__main__':
    main()

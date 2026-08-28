import os
import tkinter as tk
from tkinter import ttk


BUILD_NUMBER = '2026.03.27.08'

def build_title(title: str) -> str:
    return f"{title} | Build {BUILD_NUMBER}"

COLORS = {
    'bg': '#f2f3ee',
    'card': '#ffffff',
    'primary': '#939f4b',
    'primary_dark': '#747f39',
    'accent': '#f47721',
    'accent_dark': '#c85f18',
    'text': '#111111',
    'muted': '#5f6258',
    'line': '#d8ddca',
}


def resource_path(rel_path: str) -> str:
    import sys
    base = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return os.path.join(base, rel_path)


def apply_theme(root: tk.Misc):
    root.configure(bg=COLORS['bg'])
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    style.configure('.', font=('Segoe UI', 10))
    style.configure('Card.TFrame', background=COLORS['card'])
    style.configure('Header.TLabel', background=COLORS['bg'], foreground=COLORS['text'], font=('Segoe UI', 18, 'bold'))
    style.configure('SubHeader.TLabel', background=COLORS['bg'], foreground=COLORS['muted'], font=('Segoe UI', 10))
    style.configure('CardTitle.TLabel', background=COLORS['card'], foreground=COLORS['text'], font=('Segoe UI', 12, 'bold'))
    style.configure('CardText.TLabel', background=COLORS['card'], foreground=COLORS['muted'])
    style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'))
    style.map('Primary.TButton',
              background=[('active', COLORS['primary_dark']), ('!disabled', COLORS['primary'])],
              foreground=[('!disabled', 'white')])
    style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
    style.map('Accent.TButton',
              background=[('active', COLORS['accent_dark']), ('!disabled', COLORS['accent'])],
              foreground=[('!disabled', 'white')])
    style.configure('TLabelFrame', background=COLORS['bg'], foreground=COLORS['text'])
    style.configure('TLabelFrame.Label', background=COLORS['bg'], foreground=COLORS['text'], font=('Segoe UI', 11, 'bold'))
    style.configure('TLabelframe', background=COLORS['bg'])
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'])
    style.configure('Treeview', font=('Consolas', 10), rowheight=24)
    style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
    return style


def make_scrolled_body(root: tk.Tk):
    canvas = tk.Canvas(root, bg=COLORS['bg'], highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    body = ttk.Frame(canvas)
    body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=body, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    def _on_mousewheel(event):
        try:
            widget = root.focus_get()
            if widget and widget.winfo_class() in {'Text', 'Entry', 'TEntry'}:
                return
        except Exception:
            pass
        try:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        except Exception:
            pass

    canvas.bind_all('<MouseWheel>', _on_mousewheel)
    return body


def make_header(parent, title: str, subtitle: str, logo_rel: str = 'assets/schoel_logo.png'):
    wrap = ttk.Frame(parent)
    wrap.pack(fill='x', pady=(0, 12))
    left = ttk.Frame(wrap)
    left.pack(side='left', fill='x', expand=True)

    try:
        path = resource_path(logo_rel)
        if os.path.exists(path):
            img = tk.PhotoImage(file=path)
            try:
                img = img.subsample(max(1, img.width() // 220), max(1, img.height() // 60))
            except Exception:
                pass
            lbl = tk.Label(left, image=img, bg=COLORS['bg'])
            lbl.image = img
            lbl.pack(anchor='w', pady=(0, 8))
    except Exception:
        pass

    ttk.Label(left, text=title, style='Header.TLabel').pack(anchor='w')
    ttk.Label(left, text=subtitle, style='SubHeader.TLabel', wraplength=820, justify='left').pack(anchor='w', pady=(4, 0))
    return wrap


def section(parent, title: str):
    frame = ttk.LabelFrame(parent, text=title, padding=12)
    frame.pack(fill='x', pady=8)
    return frame


def _text_paste(widget):
    try:
        widget.event_generate('<<Paste>>')
    except Exception:
        try:
            widget.insert('insert', widget.clipboard_get())
        except Exception:
            pass
    return 'break'


def _text_copy(widget):
    try:
        widget.event_generate('<<Copy>>')
    except Exception:
        pass
    return 'break'


def _text_cut(widget):
    try:
        widget.event_generate('<<Cut>>')
    except Exception:
        pass
    return 'break'


def add_text_shortcuts(widget):
    widget.bind('<Control-v>', lambda e: _text_paste(widget))
    widget.bind('<Control-V>', lambda e: _text_paste(widget))
    widget.bind('<Control-c>', lambda e: _text_copy(widget))
    widget.bind('<Control-C>', lambda e: _text_copy(widget))
    widget.bind('<Control-x>', lambda e: _text_cut(widget))
    widget.bind('<Control-X>', lambda e: _text_cut(widget))
    widget.bind('<Button-3>', lambda e: show_text_menu(widget, e))
    return widget


def show_text_menu(widget, event):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label='Cut', command=lambda: _text_cut(widget))
    menu.add_command(label='Copy', command=lambda: _text_copy(widget))
    menu.add_command(label='Paste', command=lambda: _text_paste(widget))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def text_box(parent, width=90, height=12, font=('Consolas', 10)):
    box = tk.Text(parent, width=width, height=height, wrap='word', font=font,
                  bg='white', fg=COLORS['text'], insertbackground=COLORS['text'],
                  relief='solid', bd=1, undo=True)
    add_text_shortcuts(box)
    return box


def set_output(widget: tk.Text, text: str):
    widget.configure(state='normal')
    widget.delete('1.0', 'end')
    widget.insert('1.0', text)
    widget.configure(state='normal')


def copy_to_clipboard(root: tk.Misc, text: str):
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()

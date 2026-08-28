import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui_common import build_title

from parser_deed import parse_deed_to_steps, parse_start_bearing
from traverse import solve_traverse
from plotter import show_plot_window
from dxf_writer import export_dxf

APP_TITLE = "Interior Angle Closure, Deflection and Interior Graph"
DEFAULT_START_BEARING = "270"


try:
    from teach_parser import launch as launch_teach_parser
except Exception:
    launch_teach_parser = None

HELP_TEXT = (
    "Paste a legal description below, then set the starting bearing.\n"
    "\n"
    "Starting bearing accepts\n"
    "  Azimuth degrees like 270\n"
    "  Quadrant bearings like N 12°34'56\" E\n"
    "\n"
    "Export DXF creates layers\n"
    "  BOUNDARY for straight lines\n"
    "  CURVE for curves\n"
    "  ANGLE for angle labels\n"
)

def add_text_context_menu(widget: tk.Text):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="Select all", command=lambda: (widget.tag_add("sel", "1.0", "end-1c"), widget.mark_set("insert", "1.0"), widget.see("insert")))

    def popup(event):
        try:
            widget.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind("<Button-3>", popup)
    widget.bind("<Control-v>", lambda e: (widget.event_generate("<<Paste>>"), "break"))
    widget.bind("<Control-c>", lambda e: (widget.event_generate("<<Copy>>"), "break"))
    widget.bind("<Control-x>", lambda e: (widget.event_generate("<<Cut>>"), "break"))
    widget.bind("<Control-a>", lambda e: (widget.tag_add("sel", "1.0", "end-1c"), "break"))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title(APP_TITLE))
        self.geometry("1250x780")

        self.steps = []
        self.points = []
        self.vertices = []
        self.segment_ranges = []

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Starting bearing or azimuth").grid(row=0, column=0, sticky="w")
        self.start_bearing_var = tk.StringVar(value=DEFAULT_START_BEARING)
        ttk.Entry(top, textvariable=self.start_bearing_var, width=20).grid(row=0, column=1, padx=8, sticky="w")

        self.show_defl_var = tk.BooleanVar(value=True)
        self.show_int_var = tk.BooleanVar(value=True)
        self.show_curve_red_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(top, text="Show deflection labels", variable=self.show_defl_var).grid(row=0, column=2, padx=8, sticky="w")
        ttk.Checkbutton(top, text="Show interior labels", variable=self.show_int_var).grid(row=0, column=3, padx=8, sticky="w")
        ttk.Checkbutton(top, text="Curves in red", variable=self.show_curve_red_var).grid(row=0, column=4, padx=8, sticky="w")

        btns = ttk.Frame(top)
        btns.grid(row=0, column=5, padx=10, sticky="e")
        ttk.Button(btns, text="Load text", command=self.load_text).pack(side="left", padx=4)
        ttk.Button(btns, text="Parse and solve", command=self.parse_and_solve).pack(side="left", padx=4)
        ttk.Button(btns, text="Plot", command=self.plot).pack(side="left", padx=4)
        ttk.Button(btns, text="Export DXF", command=self.export_dxf_click).pack(side="left", padx=4)
        ttk.Button(btns, text="Teach Parser", command=self.open_teach_parser).pack(side="left", padx=4)
        ttk.Button(btns, text="Help", command=self.help).pack(side="left", padx=4)

        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Legal description text").pack(anchor="w")
        self.text = tk.Text(left, wrap="word", undo=True)
        self.text.pack(fill="both", expand=True)
        add_text_context_menu(self.text)

        right = ttk.Frame(mid, width=500)
        right.pack(side="left", fill="y", padx=(10, 0))

        ttk.Label(right, text="Output, parse log, closure").pack(anchor="w")
        self.out = tk.Text(right, wrap="word", height=10)
        self.out.pack(fill="both", expand=True)
        add_text_context_menu(self.out)

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        self.status = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status).pack(anchor="w")

    def open_teach_parser(self):
        if launch_teach_parser is None:
            messagebox.showerror('Teach Parser', 'Teach Parser module was not found in this build.')
            return
        try:
            launch_teach_parser(parent=self, seed_text=self.text.get('1.0', 'end').strip(), mode='interior_angle')
        except Exception as e:
            messagebox.showerror('Teach Parser', str(e))

    def help(self):
        messagebox.showinfo("Help", HELP_TEXT)

    def load_text(self):
        path = filedialog.askopenfilename(
            title="Choose a text file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.status.set(f"Loaded {path}")

    def parse_and_solve(self):
        deed = self.text.get("1.0", "end").strip()
        if not deed:
            messagebox.showwarning("Missing text", "Paste the legal description text first.")
            return

        start_bearing = self.start_bearing_var.get().strip()
        start_az = parse_start_bearing(start_bearing)

        steps, log = parse_deed_to_steps(deed)
        result = solve_traverse(start_az, steps)

        self.steps = steps
        self.points = result["points"]
        self.vertices = result["vertices"]
        self.segment_ranges = result["segment_ranges"]

        self.out.delete("1.0", "end")
        self.out.insert("1.0", log + "\n\n" + result["summary"])
        self.status.set("Solved and ready")

    def plot(self):
        if not self.points:
            messagebox.showwarning("Nothing to plot", "Run Parse and solve first.")
            return

        show_plot_window(
            parent=self,
            points=self.points,
            segment_ranges=self.segment_ranges,
            vertices=self.vertices,
            show_deflection=self.show_defl_var.get(),
            show_interior=self.show_int_var.get(),
            curves_in_red=self.show_curve_red_var.get()
        )

    def export_dxf_click(self):
        if not self.points:
            messagebox.showwarning("Nothing to export", "Run Parse and solve first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save DXF",
            defaultextension=".dxf",
            filetypes=[("DXF", "*.dxf")]
        )
        if not path:
            return

        export_dxf(
            path=path,
            points=self.points,
            segment_ranges=self.segment_ranges,
            vertices=self.vertices
        )
        messagebox.showinfo("DXF exported", f"Saved DXF\n{path}")

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
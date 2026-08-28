import math
import tkinter as tk
from tkinter import ttk
from ui_common import build_title

import matplotlib
matplotlib.use("TkAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

def wrap360(a: float) -> float:
    return a % 360.0

def dms_str(deg: float) -> str:
    deg = abs(deg)
    d = int(deg)
    m_float = (deg - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{d:02d}°{m:02d}'{s:05.2f}\""

def az_to_math_rad(az_deg: float) -> float:
    return math.radians(90.0 - az_deg)

def arc_points(center, az_start, az_end, clockwise, r, n=36):
    a0 = wrap360(az_start)
    a1 = wrap360(az_end)
    if clockwise:
        sweep = (a1 - a0) % 360.0
        az_list = [a0 + sweep * (k / (n - 1)) for k in range(n)]
    else:
        sweep = (a0 - a1) % 360.0
        az_list = [a0 - sweep * (k / (n - 1)) for k in range(n)]

    xs, ys = [], []
    for az in az_list:
        t = az_to_math_rad(az)
        xs.append(center[0] + r * math.cos(t))
        ys.append(center[1] + r * math.sin(t))
    return xs, ys

def _auto_arc_radius(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span <= 0:
        return 5.0
    return max(3.0, span * 0.03)

def show_plot_window(parent, points, segment_ranges, vertices, show_deflection=True, show_interior=True, curves_in_red=True):
    win = tk.Toplevel(parent)
    win.title(build_title("Traverse plot"))
    win.geometry("1020x780")

    frame = ttk.Frame(win, padding=6)
    frame.pack(fill="both", expand=True)

    fig = Figure(figsize=(7, 5), dpi=100)
    ax = fig.add_subplot(111)

    for seg in segment_ranges:
        s = seg["start_idx"]
        e = seg["end_idx"]
        pts = points[s:e+1]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if seg["type"] == "curve" and curves_in_red:
            ax.plot(xs, ys, linewidth=2, color="red")
        else:
            ax.plot(xs, ys, linewidth=2)

    all_x = [p[0] for p in points]
    all_y = [p[1] for p in points]
    ax.scatter(all_x, all_y, s=8)

    arc_r = _auto_arc_radius(points)

    for v in vertices:
        center = (v["E"], v["N"])
        az_in = v["az_in"]
        az_out = v["az_out"]
        clockwise = v["side"] == "R"

        ax_x, ax_y = arc_points(center, az_in, az_out, clockwise, arc_r, n=30)
        ax.plot(ax_x, ax_y, linewidth=1)

        mid_az = wrap360(az_in + (v["defl_abs"] / 2.0 if clockwise else -v["defl_abs"] / 2.0))
        tmid = az_to_math_rad(mid_az)
        lx = center[0] + (arc_r * 1.25) * math.cos(tmid)
        ly = center[1] + (arc_r * 1.25) * math.sin(tmid)

        parts = []
        if show_deflection:
            parts.append(f"{v['side']} {dms_str(v['defl_abs'])}")
        if show_interior:
            parts.append(f"Int {dms_str(v['interior'])}")
        label = "  ".join(parts)
        if v.get("note"):
            label = label + "  " + v["note"]

        ax.text(lx, ly, label, fontsize=9, ha="center", va="center")

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title("Traverse with Deflection and Interior Angles")
    ax.set_xlabel("Easting")
    ax.set_ylabel("Northing")

    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

    toolbar = NavigationToolbar2Tk(canvas, frame)
    toolbar.update()
    toolbar.pack(fill="x")

    win.transient(parent)
    win.grab_set()
    win.focus_force()
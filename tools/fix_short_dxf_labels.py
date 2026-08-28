import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf


def _bearing_from_points(start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)
    if dist <= 1e-9:
        return "", dist, 0.0

    az = math.degrees(math.atan2(dx, dy)) % 360.0
    if az < 90.0:
        ns, ew, ang = "N", "E", az
    elif az < 180.0:
        ns, ew, ang = "S", "E", 180.0 - az
    elif az < 270.0:
        ns, ew, ang = "S", "W", az - 180.0
    else:
        ns, ew, ang = "N", "W", 360.0 - az

    deg = int(ang)
    minute_float = (ang - deg) * 60.0
    minute = int(minute_float)
    sec = int(round((minute_float - minute) * 60.0))
    if sec == 60:
        sec = 0
        minute += 1
    if minute == 60:
        minute = 0
        deg += 1

    return f"{ns} {deg:02d}°{minute:02d}'{sec:02d}\" {ew}", dist, az


def _readable_rotation(start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    rot = math.degrees(math.atan2(dy, dx))
    if rot > 90.0:
        rot -= 180.0
    elif rot < -90.0:
        rot += 180.0
    return rot


def _drawing_span(lines):
    xs = []
    ys = []
    for line in lines:
        xs.extend([line.dxf.start.x, line.dxf.end.x])
        ys.extend([line.dxf.start.y, line.dxf.end.y])
    if not xs or not ys:
        return 100.0
    return max(max(xs) - min(xs), max(ys) - min(ys), 1.0)


def add_missing_short_labels(path, max_labeled_length=30.0):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    lines = [e for e in msp if e.dxftype() == "LINE"]
    if not lines:
        raise ValueError("No LINE entities were found in this DXF.")

    layer = "BD_SHORT_LABEL_FIX"
    if layer not in doc.layers:
        doc.layers.new(layer, dxfattribs={"color": 3})

    span = _drawing_span(lines)
    height = max(0.8, min(span * 0.008, 3.0))
    offset = height * 2.5
    added = 0

    for line in lines:
        start = line.dxf.start
        end = line.dxf.end
        p0 = (float(start.x), float(start.y))
        p1 = (float(end.x), float(end.y))
        bearing, dist, _az = _bearing_from_points(p0, p1)
        if not bearing or dist >= max_labeled_length:
            continue

        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue

        mx = (p0[0] + p1[0]) / 2.0
        my = (p0[1] + p1[1]) / 2.0
        nx = -dy / length
        ny = dx / length
        x = mx + nx * offset
        y = my + ny * offset
        rot = _readable_rotation(p0, p1)

        bearing_text = msp.add_text(
            bearing,
            dxfattribs={"height": height, "rotation": rot, "layer": layer},
        )
        bearing_text.dxf.insert = (x, y + height * 0.7)

        distance_text = msp.add_text(
            f"{dist:.2f}",
            dxfattribs={"height": height, "rotation": rot, "layer": layer},
        )
        distance_text.dxf.insert = (x, y - height * 0.7)
        added += 2

    base, ext = os.path.splitext(path)
    out_path = f"{base}_short_labels_fixed{ext or '.dxf'}"
    doc.saveas(out_path)
    return out_path, added


def main():
    root = tk.Tk()
    root.withdraw()

    path = sys.argv[1] if len(sys.argv) > 1 else filedialog.askopenfilename(
        title="Choose exported DXF to fix",
        filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        out_path, added = add_missing_short_labels(path)
    except Exception as exc:
        messagebox.showerror("DXF label fix failed", str(exc))
        raise

    messagebox.showinfo(
        "DXF label fix complete",
        f"Added {added} short-call text entities.\n\nSaved:\n{out_path}",
    )


if __name__ == "__main__":
    main()

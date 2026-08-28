import math
import os
import re
import subprocess
import sys
import threading
import time
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from ui_common import build_title
except Exception:
    def build_title(app_name, build_number=None, subtitle=None):
        title = app_name
        if build_number:
            title += f"  Build {build_number}"
        if subtitle:
            title += f"\n{subtitle}"
        return title


import ezdxf

from dxf_to_calls import (
    calls_from_vertices,
    format_calls_birmingham_lines,
    reorder_closed_polyline,
    signed_area_with_bulges,
)
from docx_writer import write_docx_paragraphs
from rtf_output import write_rtf_lines, write_txt_lines

APP_TITLE = "Birmingham Legal Description Writer from DXF"
DEFAULT_TITLE = "LEGAL DESCRIPTION"
DEFAULT_PARCEL = "(Parcel 1)"
DEFAULT_LOCATION = (
    "A parcel of land situated in the N.E. 1/4 of the S.E. 1/4 of Section XX, "
    "Township XX South, Range XX West, Jefferson County, Alabama, being more particularly described as follows:"
)
DEFAULT_BEGIN = ""
AREA_STYLES = {
    "Acres only": "acres",
    "Square feet and acres": "both",
}
COLORS = {
    "bg": "#f2f3ee",
    "panel": "#ffffff",
    "line": "#d8ddca",
    "primary": "#939f4b",
    "primary_dark": "#747f39",
    "accent": "#f47721",
    "accent_dark": "#c85f18",
    "text": "#111111",
    "muted": "#5f6258",
    "canvas": "#ffffff",
    "highlight": "#f47721",
    "readaloud": "#f6c99c",
}


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def split_for_readaloud(text: str, highlight_mode: bool = False):
    def _append(chunks, source_text, start_offset, end_offset):
        spoken = re.sub(r"\s+", " ", source_text[start_offset:end_offset]).strip()
        if spoken:
            chunks.append({"text": spoken, "start": start_offset, "end": end_offset})

    if not text or not text.strip():
        return []

    chunks = []
    offset = 0
    for raw_line in text.splitlines(True):
        body = raw_line.rstrip("\r\n")
        if not body.strip():
            offset += len(raw_line)
            continue

        line_start = offset + (len(body) - len(body.lstrip()))
        line_end = offset + len(body.rstrip())
        line_text = text[line_start:line_end]

        if ";" not in line_text:
            _append(chunks, text, line_start, line_end)
            offset += len(raw_line)
            continue

        for part in re.finditer(r".+?(?:;(?=\s|$)|$)", line_text, flags=re.S):
            raw_part = part.group(0)
            if not raw_part.strip():
                continue
            part_start = line_start + part.start() + (len(raw_part) - len(raw_part.lstrip()))
            part_end = line_start + part.end() - (len(raw_part) - len(raw_part.rstrip()))
            _append(chunks, text, part_start, part_end)

        offset += len(raw_line)

    return chunks


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title(APP_TITLE))
        self.geometry("1180x940")
        self.minsize(1080, 780)

        self.dxf_path = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.direction = tk.StringVar(value="CCW")

        self.title_line = tk.StringVar(value=DEFAULT_TITLE)
        self.parcel_line = tk.StringVar(value=DEFAULT_PARCEL)
        self.area_style = tk.StringVar(value="Acres only")
        self.auto_area = tk.BooleanVar(value=True)
        self.area_text = tk.StringVar(value="")

        self.poly_choice = tk.StringVar()
        self.polylines = []
        self.start_index = 0
        self.calls_lines = []
        self.computed_area_sqft = 0.0
        self.view_vertices = []

        self.speech_status = tk.StringVar(value="Read aloud ready")
        self._speech_thread = None
        self._speech_pause_event = threading.Event()
        self._speech_stop_event = threading.Event()
        self._speech_process = None
        self._readaloud_chunks = []
        self._logo_image = None
        self._logo_display = None

        self._apply_branding()
        self._apply_theme()
        self._build_ui()
        self.location_text.insert("1.0", DEFAULT_LOCATION)
        self.begin_text.insert("1.0", DEFAULT_BEGIN)
        self._wire_preview_updates()
        try:
            self.direction.trace_add("write", lambda *_a: self.refresh_calls())
        except Exception:
            pass

    def _apply_theme(self):
        self.configure(bg=COLORS["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 15, "bold"))
        style.configure("TButton", padding=(10, 6), font=("Segoe UI", 10, "bold"))
        style.map(
            "TButton",
            background=[("active", COLORS["primary_dark"]), ("!disabled", COLORS["primary"])],
            foreground=[("!disabled", "white")],
        )
        style.configure("TCheckbutton", background=COLORS["bg"], foreground=COLORS["text"])
        style.map("TCheckbutton", background=[("active", COLORS["bg"])])
        style.configure("TRadiobutton", background=COLORS["bg"], foreground=COLORS["text"])
        style.map("TRadiobutton", background=[("active", COLORS["bg"])])
        style.configure("TEntry", fieldbackground=COLORS["panel"], foreground=COLORS["text"], bordercolor=COLORS["line"])
        style.configure("TCombobox", fieldbackground=COLORS["panel"], foreground=COLORS["text"])

    def _apply_branding(self):
        logo_png = resource_path("schoel_logo.png")
        logo_ico = resource_path("schoel_logo.ico")
        try:
            if os.path.exists(logo_png):
                self._logo_image = tk.PhotoImage(file=logo_png)
                self.iconphoto(True, self._logo_image)
        except Exception:
            self._logo_image = None
        try:
            if os.name == "nt" and os.path.exists(logo_ico):
                self.iconbitmap(default=logo_ico)
        except Exception:
            pass

    def _build_ui(self):
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        banner = ttk.Frame(outer)
        banner.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))
        self._build_banner(banner)

        top = ttk.Frame(outer)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        ttk.Label(top, text="Birmingham Legal Description Writer  |  Build 2026.03.27.15", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(4, 8)
        )

        ttk.Button(top, text="Select DXF", command=self.select_dxf).grid(row=1, column=0, padx=5, pady=4, sticky="w")
        ttk.Entry(top, textvariable=self.dxf_path, width=80).grid(row=1, column=1, padx=5, pady=4, sticky="we")

        ttk.Button(top, text="Select Output Folder", command=self.select_out_dir).grid(row=2, column=0, padx=5, pady=4, sticky="w")
        ttk.Entry(top, textvariable=self.out_dir, width=80).grid(row=2, column=1, padx=5, pady=4, sticky="we")

        ttk.Label(top, text="Boundary polyline:").grid(row=3, column=0, padx=5, pady=4, sticky="w")
        self.combo = ttk.Combobox(top, textvariable=self.poly_choice, width=77, state="readonly")
        self.combo.grid(row=3, column=1, padx=5, pady=4, sticky="we")
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self.draw_selected_polyline())

        ttk.Label(top, text="Traverse direction:").grid(row=4, column=0, padx=5, pady=4, sticky="w")
        dir_frame = ttk.Frame(top)
        dir_frame.grid(row=4, column=1, padx=5, pady=4, sticky="w")
        ttk.Radiobutton(dir_frame, text="Counterclockwise", variable=self.direction, value="CCW", command=self.refresh_calls).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(dir_frame, text="Clockwise", variable=self.direction, value="CW", command=self.refresh_calls).pack(side=tk.LEFT, padx=6)

        tp = ttk.Frame(top)
        tp.grid(row=5, column=1, padx=5, pady=4, sticky="we")
        ttk.Label(top, text="Title and parcel label:").grid(row=5, column=0, padx=5, pady=4, sticky="nw")
        ttk.Entry(tp, textvariable=self.title_line, width=35).pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        ttk.Entry(tp, textvariable=self.parcel_line, width=35).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(top, text="Location paragraph:").grid(row=6, column=0, padx=5, pady=4, sticky="nw")
        self.location_text = tk.Text(top, height=3, wrap="word", bg=COLORS["panel"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="solid", bd=1)
        self.location_text.grid(row=6, column=1, padx=5, pady=4, sticky="we")

        ttk.Label(top, text="Begin / commence paragraph:").grid(row=7, column=0, padx=5, pady=4, sticky="nw")
        self.begin_text = tk.Text(top, height=4, wrap="word", bg=COLORS["panel"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="solid", bd=1)
        self.begin_text.grid(row=7, column=1, padx=5, pady=4, sticky="we")

        area_row = ttk.Frame(top)
        area_row.grid(row=8, column=1, padx=5, pady=4, sticky="we")
        ttk.Checkbutton(area_row, text="Auto area", variable=self.auto_area, command=self.refresh_calls).pack(side=tk.LEFT)
        ttk.Combobox(area_row, values=list(AREA_STYLES.keys()), textvariable=self.area_style, width=22, state="readonly").pack(side=tk.LEFT, padx=8)
        ttk.Entry(area_row, textvariable=self.area_text, width=60).pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        ttk.Label(top, text="Area sentence:").grid(row=8, column=0, padx=5, pady=4, sticky="w")

        btn_row = ttk.Frame(top)
        btn_row.grid(row=9, column=1, padx=5, pady=(8, 2), sticky="e")
        ttk.Button(btn_row, text="Export DOCX RTF TXT", command=self.export_files).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_row, text="Copy Body Paragraph", command=self.copy_body_paragraph).pack(side=tk.RIGHT, padx=6)

        audio_row = ttk.Frame(top)
        audio_row.grid(row=10, column=1, padx=5, pady=(2, 8), sticky="we")
        ttk.Button(audio_row, text="Read Aloud", command=self.start_readaloud).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(audio_row, text="Play by Highlight", command=self.start_highlight_readaloud).pack(side=tk.LEFT, padx=6)
        ttk.Button(audio_row, text="Pause", command=self.pause_readaloud).pack(side=tk.LEFT, padx=6)
        ttk.Button(audio_row, text="Resume", command=self.resume_readaloud).pack(side=tk.LEFT, padx=6)
        ttk.Button(audio_row, text="Stop", command=self.stop_readaloud).pack(side=tk.LEFT, padx=6)
        ttk.Label(audio_row, textvariable=self.speech_status).pack(side=tk.LEFT, padx=12)

        top.columnconfigure(1, weight=1)

        mid = ttk.Frame(outer)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text="Click a vertex to set the Point of Beginning").pack(anchor="w")
        self.canvas = tk.Canvas(left, bg=COLORS["canvas"], highlightthickness=1, highlightbackground=COLORS["line"])
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click_canvas)
        self.canvas.bind("<Configure>", lambda _e: self.draw_selected_polyline())

        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        ttk.Label(right, text="Preview:").pack(anchor="w")
        preview_frame = ttk.Frame(right)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview = tk.Text(
            preview_frame,
            wrap="word",
            yscrollcommand=preview_scroll.set,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="solid",
            bd=1,
        )
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.config(command=self.preview.yview)
        self.preview.tag_configure("readaloud_active", background=COLORS["readaloud"], foreground=COLORS["text"])

    def _build_banner(self, parent):
        logo_path = resource_path("schoel_logo.png")
        if not os.path.exists(logo_path):
            return
        try:
            raw = tk.PhotoImage(file=logo_path)
            self._logo_display = raw
            max_width = 520
            if raw.width() > max_width:
                factor = max(1, math.ceil(raw.width() / max_width))
                self._logo_display = raw.subsample(factor, factor)
            ttk.Label(parent, image=self._logo_display).pack(anchor="w")
        except Exception:
            self._logo_display = None

    def _wire_preview_updates(self):
        self.location_text.bind("<KeyRelease>", lambda _e: self.refresh_preview_only())
        self.begin_text.bind("<KeyRelease>", lambda _e: self.refresh_preview_only())
        self.location_text.bind("<FocusOut>", lambda _e: self.refresh_preview_only())
        self.begin_text.bind("<FocusOut>", lambda _e: self.refresh_preview_only())
        for var in (self.title_line, self.parcel_line, self.area_style, self.area_text):
            try:
                var.trace_add("write", lambda *_a: self.refresh_preview_only())
            except Exception:
                var.trace("w", lambda *_a: self.refresh_preview_only())

    def select_dxf(self):
        path = filedialog.askopenfilename(title="Select DXF", filetypes=[("DXF files", "*.dxf")])
        if not path:
            return
        self.dxf_path.set(path)
        self.load_dxf_polylines()

    def select_out_dir(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.out_dir.set(path)

    def _normalize_closed(self, vertices, bulges):
        if len(vertices) > 2 and abs(vertices[0][0] - vertices[-1][0]) < 1e-9 and abs(vertices[0][1] - vertices[-1][1]) < 1e-9:
            return vertices[:-1], bulges[:-1]
        return vertices, bulges

    def load_dxf_polylines(self):
        self.polylines = []
        try:
            doc = ezdxf.readfile(self.dxf_path.get())
        except Exception as exc:
            messagebox.showerror("DXF read error", str(exc))
            return

        msp = doc.modelspace()
        count = 0
        for entity in msp:
            if entity.dxftype() == "LWPOLYLINE":
                if not entity.closed:
                    continue
                pts = []
                bulges = []
                for vertex in entity:
                    pts.append((float(vertex[0]), float(vertex[1])))
                    bulges.append(float(vertex[4] if len(vertex) > 4 else 0.0))
                pts, bulges = self._normalize_closed(pts, bulges)
                if len(pts) < 3:
                    continue
                count += 1
                name = f"{count}: LWPOLYLINE layer {entity.dxf.layer} handle {entity.dxf.handle}"
                self.polylines.append({"name": name, "vertices": pts, "bulges": bulges})
            elif entity.dxftype() == "POLYLINE":
                if not entity.is_closed:
                    continue
                pts = []
                bulges = []
                for vertex in list(entity.vertices()):
                    pts.append((float(vertex.dxf.location.x), float(vertex.dxf.location.y)))
                    bulges.append(float(getattr(vertex.dxf, "bulge", 0.0)))
                pts, bulges = self._normalize_closed(pts, bulges)
                if len(pts) < 3:
                    continue
                count += 1
                name = f"{count}: POLYLINE layer {entity.dxf.layer} handle {entity.dxf.handle}"
                self.polylines.append({"name": name, "vertices": pts, "bulges": bulges})

        if not self.polylines:
            messagebox.showwarning("No closed polylines found", "No closed LWPOLYLINE or POLYLINE objects were found in modelspace.")
            return

        self.combo["values"] = [poly["name"] for poly in self.polylines]
        self.poly_choice.set(self.polylines[0]["name"])
        self.start_index = 0
        self.draw_selected_polyline()
        self.refresh_calls()

    def selected_poly(self):
        name = self.poly_choice.get()
        for poly in self.polylines:
            if poly["name"] == name:
                return poly
        return None

    def _compute_view_transform(self, vertices):
        width = max(10, self.canvas.winfo_width())
        height = max(10, self.canvas.winfo_height())
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 1.0)
        dy = max(maxy - miny, 1.0)
        pad = 30
        scale = min((width - 2 * pad) / dx, (height - 2 * pad) / dy)
        return scale, (minx, miny, maxx, maxy), pad

    def _world_to_screen(self, x, y, scale, bounds, pad, height):
        minx, miny, _, _ = bounds
        sx = pad + (x - minx) * scale
        sy = height - (pad + (y - miny) * scale)
        return sx, sy

    def draw_selected_polyline(self):
        poly = self.selected_poly()
        if not poly:
            return
        self.canvas.delete("all")
        vertices = poly["vertices"]
        if len(vertices) < 2:
            return

        scale, bounds, pad = self._compute_view_transform(vertices)
        height = max(10, self.canvas.winfo_height())
        self.view_vertices = [self._world_to_screen(x, y, scale, bounds, pad, height) for x, y in vertices]

        pts = []
        for sx, sy in self.view_vertices:
            pts.extend([sx, sy])
        pts.extend([self.view_vertices[0][0], self.view_vertices[0][1]])
        self.canvas.create_line(*pts, fill="black", width=2)

        for sx, sy in self.view_vertices:
            self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill="white", outline="black")

        if self.start_index is not None and 0 <= self.start_index < len(self.view_vertices):
            sx, sy = self.view_vertices[self.start_index]
            self.canvas.create_oval(sx - 9, sy - 9, sx + 9, sy + 9, fill="", outline=COLORS["accent"], width=3)

    def on_click_canvas(self, event):
        if not self.view_vertices:
            return
        best_index = 0
        best_dist = None
        for idx, (sx, sy) in enumerate(self.view_vertices):
            d = math.hypot(sx - event.x, sy - event.y)
            if best_dist is None or d < best_dist:
                best_dist = d
                best_index = idx
        self.start_index = best_index
        self.draw_selected_polyline()
        self.refresh_calls()

    def _area_sentence(self) -> str:
        acres = self.computed_area_sqft / 43560.0
        area_mode = AREA_STYLES.get(self.area_style.get(), "acres")
        if area_mode == "both":
            return f"Containing {round(self.computed_area_sqft):,.0f} square feet or {acres:.3f} acres."
        return f"Containing {acres:.3f} acres."

    def _body_paragraph(self) -> str:
        begin = self.begin_text.get("1.0", tk.END).strip().replace("\n", " ")
        calls = " ".join(line.strip() for line in self.calls_lines if line.strip())
        if begin and calls:
            return f"{begin} {calls}".strip()
        return begin or calls

    def _build_preview_lines(self):
        location = self.location_text.get("1.0", tk.END).strip()
        body = self._body_paragraph()
        area = (self.area_text.get() or "").strip()
        lines = [self.title_line.get().strip(), self.parcel_line.get().strip(), ""]
        if location:
            lines.append(location)
        if body:
            lines.append(body)
        if area:
            lines.extend(["", area])
        return lines

    def refresh_preview_only(self):
        if self.auto_area.get() and self.computed_area_sqft > 0:
            self.area_text.set(self._area_sentence())
        lines = self._build_preview_lines()
        self.preview.delete("1.0", tk.END)
        for line in lines:
            self.preview.insert(tk.END, line + "\n")

    def refresh_calls(self):
        poly = self.selected_poly()
        if not poly:
            self.preview.delete("1.0", tk.END)
            return
        if self.start_index is None:
            self.start_index = 0

        try:
            ordered_vertices, ordered_bulges = reorder_closed_polyline(
                poly["vertices"], poly["bulges"], self.start_index, self.direction.get()
            )
            calls = calls_from_vertices(ordered_vertices, ordered_bulges)
            self.calls_lines = format_calls_birmingham_lines(calls, decimals=2, close_with_pob=True, preferred_turn=None)
            self.computed_area_sqft = abs(signed_area_with_bulges(ordered_vertices, ordered_bulges))
        except Exception as exc:
            messagebox.showerror("Call generation error", str(exc))
            return

        if self.auto_area.get():
            self.area_text.set(self._area_sentence())
        self.refresh_preview_only()

    def copy_body_paragraph(self):
        body = self._body_paragraph().strip()
        if not body:
            return
        self.clipboard_clear()
        self.clipboard_append(body)
        messagebox.showinfo("Copied", "Body paragraph copied to clipboard.")

    def _build_docx_paragraphs(self, lines):
        paragraphs = []
        for idx, line in enumerate(lines):
            if line == "":
                paragraphs.append({"text": "", "align": "left"})
                continue
            if idx in (0, 1):
                paragraphs.append({"text": line, "align": "center", "bold": True})
                continue
            if idx == 3:
                paragraphs.append({"text": line, "align": "left"})
                continue
            if idx == 4:
                paragraphs.append({"text": line, "align": "justify"})
                continue
            paragraphs.append({"text": line, "align": "left"})
        return paragraphs

    def export_files(self):
        preview_text = self.preview.get("1.0", "end-1c")
        if not preview_text.strip():
            messagebox.showwarning("Nothing to export", "Preview is empty. Generate a draft first.")
            return
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("Output folder", "Select an output folder first.")
            return

        lines = preview_text.splitlines()
        docx_path = os.path.join(out_dir, "OUTPUT_birmingham_legal_description.docx")
        rtf_path = os.path.join(out_dir, "OUTPUT_birmingham_legal_description.rtf")
        txt_path = os.path.join(out_dir, "OUTPUT_birmingham_legal_description.txt")

        try:
            write_docx_paragraphs(docx_path, self._build_docx_paragraphs(lines))
            write_rtf_lines(rtf_path, lines)
            write_txt_lines(txt_path, lines)
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))
            return

        messagebox.showinfo("Done", f"Saved\n{docx_path}\n{rtf_path}\n{txt_path}")

    def _set_speech_status(self, text: str):
        self.after(0, lambda: self.speech_status.set(text))

    def _clear_highlight(self):
        self.after(0, lambda: self.preview.tag_remove("readaloud_active", "1.0", tk.END))

    def _highlight_chunk(self, chunk):
        def _apply():
            self.preview.tag_remove("readaloud_active", "1.0", tk.END)
            start_idx = f"1.0+{chunk['start']}c"
            end_idx = f"1.0+{chunk['end']}c"
            self.preview.tag_add("readaloud_active", start_idx, end_idx)
            self.preview.mark_set("insert", start_idx)
            self.preview.see("insert")
            self.preview.update_idletasks()
        self.after(0, _apply)

    def _speak_with_powershell(self, text: str):
        if os.name != "nt":
            raise RuntimeError("Read aloud requires Windows on the office EXE.")

        fd_text, text_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd_text)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)

        fd_script, script_path = tempfile.mkstemp(suffix=".ps1")
        os.close(fd_script)
        script = (
            '$ErrorActionPreference = "Stop"\n'
            'Add-Type -AssemblyName System.Speech\n'
            '$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer\n'
            '$voice.Rate = 2\n'
            '$voice.Volume = 100\n'
            f"$text = [System.IO.File]::ReadAllText('{text_path.replace(chr(39), chr(39) * 2)}')\n"
            '$voice.Speak($text)\n'
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = 0

        candidates = [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "powershell.exe",
        ]
        last_error = None
        try:
            for exe in candidates:
                try:
                    self._speech_process = subprocess.Popen(
                        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", script_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creationflags,
                        startupinfo=startupinfo,
                    )
                    self._speech_process.wait()
                    return
                except FileNotFoundError as exc:
                    last_error = exc
                    continue
        finally:
            self._speech_process = None
            for path in (text_path, script_path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        raise RuntimeError("Windows PowerShell speech is not available on this computer.") from last_error

    def _sanitize_for_speech(self, text: str) -> str:
        cleaned = text
        replacements = {
            "º": " degrees",
            "°": " degrees",
            "’": "'",
            "“": '"',
            "”": '"',
        }
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _speak_chunk(self, text: str):
        text = self._sanitize_for_speech(text)
        self._speak_with_powershell(text)

    def _begin_readaloud(self, highlight: bool):
        text = self.preview.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("Read aloud", "Preview is empty.")
            return
        if self._speech_thread and self._speech_thread.is_alive():
            messagebox.showinfo("Read aloud", "Read aloud is already running.")
            return
        self._readaloud_chunks = split_for_readaloud(text, highlight_mode=highlight)
        if not self._readaloud_chunks:
            messagebox.showwarning("Read aloud", "Preview is empty.")
            return
        self._speech_pause_event.clear()
        self._speech_stop_event.clear()
        self._clear_highlight()
        status = "Playing by highlight" if highlight else "Reading preview"
        self._set_speech_status(status)
        self._speech_thread = threading.Thread(target=self._readaloud_worker, args=(highlight,), daemon=True)
        self._speech_thread.start()

    def start_readaloud(self):
        self._begin_readaloud(highlight=False)

    def start_highlight_readaloud(self):
        self._begin_readaloud(highlight=True)

    def pause_readaloud(self):
        if self._speech_thread and self._speech_thread.is_alive():
            self._speech_pause_event.set()
            try:
                if self._speech_process is not None and self._speech_process.poll() is None:
                    self._speech_process.kill()
            except Exception:
                pass
            self.speech_status.set("Paused")

    def resume_readaloud(self):
        if self._speech_thread and self._speech_thread.is_alive():
            self._speech_pause_event.clear()
            if self.preview.tag_ranges("readaloud_active"):
                self.speech_status.set("Playing by highlight")
            else:
                self.speech_status.set("Reading preview")

    def stop_readaloud(self):
        if self._speech_thread and self._speech_thread.is_alive():
            self._speech_stop_event.set()
            try:
                if self._speech_process is not None and self._speech_process.poll() is None:
                    self._speech_process.kill()
            except Exception:
                pass
            self.speech_status.set("Stopping")
        else:
            self._clear_highlight()
            self.speech_status.set("Read aloud ready")

    def _readaloud_worker(self, highlight: bool):
        try:
            if not self._readaloud_chunks:
                self._set_speech_status("Read aloud ready")
                return
            for chunk in self._readaloud_chunks:
                while self._speech_pause_event.is_set() and not self._speech_stop_event.is_set():
                    time.sleep(0.1)
                if self._speech_stop_event.is_set():
                    break
                if highlight:
                    self._highlight_chunk(chunk)
                    self._set_speech_status("Playing by highlight")
                else:
                    self._clear_highlight()
                    self._set_speech_status("Reading preview")
                self._speak_chunk(chunk["text"])
                if self._speech_stop_event.is_set():
                    break
            self._clear_highlight()
            final_status = "Stopped" if self._speech_stop_event.is_set() else "Read aloud ready"
            self._set_speech_status(final_status)
        except Exception as exc:
            self._clear_highlight()
            self._set_speech_status("Read aloud unavailable")
            self.after(0, lambda: messagebox.showerror("Read aloud error", str(exc)))
        finally:
            self._speech_pause_event.clear()
            self._speech_stop_event.clear()
            self._speech_process = None


if __name__ == "__main__":
    App().mainloop()

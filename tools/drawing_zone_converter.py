import math
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard
from geometry_utils import USFT_PER_M

TITLE = 'Drawing Zone Converter'
EAST_M = 'EPSG:26929'
WEST_M = 'EPSG:26930'

try:
    from pyproj import Transformer
except Exception:
    Transformer = None

try:
    import ezdxf
except Exception:
    ezdxf = None

SUPPORTED_TYPES = {
    'POINT', 'LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'TEXT', 'MTEXT',
    'INSERT', 'ELLIPSE', 'SPLINE', 'IMAGE', 'SOLID', 'TRACE', '3DFACE', 'DIMENSION',
    'LEADER', 'MLINE', 'HATCH'
}


def zone_crs(zone: str) -> str:
    return EAST_M if zone == 'East' else WEST_M


def feet_to_m(value: float) -> float:
    return float(value) / USFT_PER_M


def m_to_feet(value: float) -> float:
    return float(value) * USFT_PER_M


def clean_num(text: str, default: float = 0.0) -> float:
    text = (text or '').strip().replace(',', '')
    return float(text) if text else default


def build_transformer(source_zone: str, target_zone: str):
    if Transformer is None:
        raise RuntimeError('pyproj is not installed. Run pip install pyproj before building the suite.')
    return Transformer.from_crs(zone_crs(source_zone), zone_crs(target_zone), always_xy=True)


def transform_xy(transformer, x_usft: float, y_usft: float):
    x_m = feet_to_m(x_usft)
    y_m = feet_to_m(y_usft)
    new_x_m, new_y_m = transformer.transform(x_m, y_m)
    return m_to_feet(new_x_m), m_to_feet(new_y_m)


def rotate_angle_deg(angle_deg: float, rotation_deg: float) -> float:
    return (float(angle_deg) + float(rotation_deg)) % 360.0


def transform_point_manual(x: float, y: float, dx: float, dy: float, scale: float, rotation_deg: float):
    ang = math.radians(rotation_deg)
    xr = x * scale
    yr = y * scale
    xn = xr * math.cos(ang) - yr * math.sin(ang) + dx
    yn = xr * math.sin(ang) + yr * math.cos(ang) + dy
    return xn, yn


def get_oda_executable(hint: str = '') -> str | None:
    candidates = []
    if hint:
        candidates.append(hint)
    candidates.extend([
        r'C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe',
        r'C:\\Program Files\\Open Design Alliance\\ODAFileConverter\\ODAFileConverter.exe',
    ])
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def dwg_to_dxf_via_oda(dwg_path: str, oda_path: str):
    dwg = Path(dwg_path)
    temp_in = Path(tempfile.mkdtemp(prefix='schoel_dwg_in_'))
    temp_out = Path(tempfile.mkdtemp(prefix='schoel_dwg_out_'))
    working_dwg = temp_in / dwg.name
    shutil.copy2(dwg, working_dwg)
    cmd = [oda_path, str(temp_in), str(temp_out), 'ACAD2018', 'DXF', '1', '1', '*.dwg']
    subprocess.run(cmd, check=True, capture_output=True)
    out_dxf = temp_out / (dwg.stem + '.dxf')
    if not out_dxf.exists():
        raise RuntimeError('ODA File Converter did not produce a DXF output file.')
    return str(out_dxf), str(temp_in), str(temp_out)


def dxf_to_dwg_via_oda(dxf_path: str, oda_path: str, target_path: str):
    dxf = Path(dxf_path)
    temp_in = Path(tempfile.mkdtemp(prefix='schoel_dxf_in_'))
    temp_out = Path(tempfile.mkdtemp(prefix='schoel_dxf_out_'))
    working_dxf = temp_in / dxf.name
    shutil.copy2(dxf, working_dxf)
    cmd = [oda_path, str(temp_in), str(temp_out), 'ACAD2018', 'DWG', '1', '1', '*.dxf']
    subprocess.run(cmd, check=True, capture_output=True)
    out_dwg = temp_out / (dxf.stem + '.dwg')
    if not out_dwg.exists():
        raise RuntimeError('ODA File Converter did not produce a DWG output file.')
    shutil.copy2(out_dwg, target_path)
    return str(out_dwg), str(temp_in), str(temp_out)


def transform_insert_rotation(entity, rotation_delta: float):
    try:
        entity.dxf.rotation = rotate_angle_deg(getattr(entity.dxf, 'rotation', 0.0), rotation_delta)
    except Exception:
        pass


def transform_text_like(entity, new_x: float, new_y: float, rotation_delta: float):
    try:
        entity.dxf.insert = (new_x, new_y, 0.0)
    except Exception:
        pass
    try:
        entity.dxf.rotation = rotate_angle_deg(getattr(entity.dxf, 'rotation', 0.0), rotation_delta)
    except Exception:
        pass


def transform_entity_projection(entity, transformer):
    kind = entity.dxftype()
    changed = 0
    try:
        if kind == 'POINT':
            x, y, z = entity.dxf.location
            nx, ny = transform_xy(transformer, x, y)
            entity.dxf.location = (nx, ny, z)
            return 1
        if kind == 'LINE':
            sx, sy, sz = entity.dxf.start
            ex, ey, ez = entity.dxf.end
            nsx, nsy = transform_xy(transformer, sx, sy)
            nex, ney = transform_xy(transformer, ex, ey)
            entity.dxf.start = (nsx, nsy, sz)
            entity.dxf.end = (nex, ney, ez)
            return 1
        if kind == 'LWPOLYLINE':
            pts = list(entity.get_points('xyseb'))
            new_pts = []
            for p in pts:
                x, y = p[0], p[1]
                nx, ny = transform_xy(transformer, x, y)
                new_pts.append((nx, ny, *p[2:]))
            entity.set_points(new_pts, format='xyseb')
            return 1
        if kind == 'POLYLINE':
            for v in entity.vertices:
                x, y, z = v.dxf.location
                nx, ny = transform_xy(transformer, x, y)
                v.dxf.location = (nx, ny, z)
                changed = 1
            return changed
        if kind in {'CIRCLE', 'ARC', 'ELLIPSE'}:
            cx, cy, cz = entity.dxf.center
            ncx, ncy = transform_xy(transformer, cx, cy)
            entity.dxf.center = (ncx, ncy, cz)
            return 1
        if kind == 'INSERT':
            x, y, z = entity.dxf.insert
            nx, ny = transform_xy(transformer, x, y)
            entity.dxf.insert = (nx, ny, z)
            return 1
        if kind in {'TEXT', 'MTEXT'}:
            x, y, z = entity.dxf.insert
            nx, ny = transform_xy(transformer, x, y)
            entity.dxf.insert = (nx, ny, z)
            return 1
        if kind == 'IMAGE':
            x, y, z = entity.dxf.insert
            nx, ny = transform_xy(transformer, x, y)
            entity.dxf.insert = (nx, ny, z)
            return 1
        if kind == 'HATCH':
            # leave hatch pattern geometry untouched if direct edit is unavailable
            return 0
    except Exception:
        return 0
    return 0


def transform_entity_manual(entity, dx: float, dy: float, scale: float, rotation_deg: float):
    kind = entity.dxftype()
    changed = 0
    try:
        if kind == 'POINT':
            x, y, z = entity.dxf.location
            nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
            entity.dxf.location = (nx, ny, z)
            return 1
        if kind == 'LINE':
            sx, sy, sz = entity.dxf.start
            ex, ey, ez = entity.dxf.end
            nsx, nsy = transform_point_manual(sx, sy, dx, dy, scale, rotation_deg)
            nex, ney = transform_point_manual(ex, ey, dx, dy, scale, rotation_deg)
            entity.dxf.start = (nsx, nsy, sz)
            entity.dxf.end = (nex, ney, ez)
            return 1
        if kind == 'LWPOLYLINE':
            pts = list(entity.get_points('xyseb'))
            new_pts = []
            for p in pts:
                x, y = p[0], p[1]
                nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
                new_pts.append((nx, ny, *p[2:]))
            entity.set_points(new_pts, format='xyseb')
            return 1
        if kind == 'POLYLINE':
            for v in entity.vertices:
                x, y, z = v.dxf.location
                nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
                v.dxf.location = (nx, ny, z)
                changed = 1
            return changed
        if kind in {'CIRCLE', 'ARC', 'ELLIPSE'}:
            cx, cy, cz = entity.dxf.center
            ncx, ncy = transform_point_manual(cx, cy, dx, dy, scale, rotation_deg)
            entity.dxf.center = (ncx, ncy, cz)
            try:
                entity.dxf.radius = float(entity.dxf.radius) * scale
            except Exception:
                pass
            if kind == 'ARC':
                try:
                    entity.dxf.start_angle = rotate_angle_deg(entity.dxf.start_angle, rotation_deg)
                    entity.dxf.end_angle = rotate_angle_deg(entity.dxf.end_angle, rotation_deg)
                except Exception:
                    pass
            return 1
        if kind == 'INSERT':
            x, y, z = entity.dxf.insert
            nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
            entity.dxf.insert = (nx, ny, z)
            try:
                entity.dxf.xscale = float(getattr(entity.dxf, 'xscale', 1.0)) * scale
                entity.dxf.yscale = float(getattr(entity.dxf, 'yscale', 1.0)) * scale
                if hasattr(entity.dxf, 'zscale'):
                    entity.dxf.zscale = float(getattr(entity.dxf, 'zscale', 1.0)) * scale
            except Exception:
                pass
            transform_insert_rotation(entity, rotation_deg)
            return 1
        if kind in {'TEXT', 'MTEXT'}:
            x, y, z = entity.dxf.insert
            nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
            transform_text_like(entity, nx, ny, rotation_deg)
            try:
                entity.dxf.height = float(getattr(entity.dxf, 'height', 0.0)) * scale
            except Exception:
                pass
            try:
                entity.dxf.char_height = float(getattr(entity.dxf, 'char_height', 0.0)) * scale
            except Exception:
                pass
            return 1
        if kind == 'IMAGE':
            x, y, z = entity.dxf.insert
            nx, ny = transform_point_manual(x, y, dx, dy, scale, rotation_deg)
            entity.dxf.insert = (nx, ny, z)
            transform_insert_rotation(entity, rotation_deg)
            try:
                entity.dxf.u_pixel = tuple(v * scale for v in entity.dxf.u_pixel)
                entity.dxf.v_pixel = tuple(v * scale for v in entity.dxf.v_pixel)
            except Exception:
                pass
            return 1
        if kind == 'HATCH':
            return 0
    except Exception:
        return 0
    return 0


def process_dxf(in_path: str, out_path: str, mode: str, source_zone: str, target_zone: str, dx: float, dy: float, scale: float, rotation_deg: float):
    if ezdxf is None:
        raise RuntimeError('ezdxf is not installed. Run pip install ezdxf before building the suite.')
    doc = ezdxf.readfile(in_path)
    msp = doc.modelspace()
    count = 0
    skipped = {}
    transformer = None
    if mode == 'State Plane East/West':
        transformer = build_transformer(source_zone, target_zone)
    for entity in msp:
        kind = entity.dxftype()
        if kind not in SUPPORTED_TYPES:
            skipped[kind] = skipped.get(kind, 0) + 1
            continue
        changed = 0
        if mode == 'State Plane East/West':
            changed = transform_entity_projection(entity, transformer)
        else:
            changed = transform_entity_manual(entity, dx, dy, scale, rotation_deg)
        count += changed
        if not changed and kind not in {'HATCH'}:
            skipped[kind] = skipped.get(kind, 0) + 1
    doc.saveas(out_path)
    return count, skipped


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(build_title(TITLE))
        self.geometry('1120x920')
        apply_theme(self)

        body = make_scrolled_body(self)
        make_header(body, TITLE, 'Convert DXF drawings directly between Alabama East and Alabama West in U.S. survey foot. DWG is supported through ODA File Converter if it is installed on the machine.')

        files = section(body, 'Input and Output')
        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.oda_var = tk.StringVar()
        self.mode_var = tk.StringVar(value='State Plane East/West')
        self.source_zone = tk.StringVar(value='East')
        self.target_zone = tk.StringVar(value='West')

        ttk.Label(files, text='Input drawing (.dxf or .dwg)').pack(anchor='w')
        row = ttk.Frame(files)
        row.pack(fill='x', pady=(4, 8))
        ttk.Entry(row, textvariable=self.in_var, width=96).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse', style='Primary.TButton', command=self.browse_in).pack(side='left', padx=(8, 0))

        ttk.Label(files, text='Output drawing').pack(anchor='w')
        row2 = ttk.Frame(files)
        row2.pack(fill='x', pady=(4, 8))
        ttk.Entry(row2, textvariable=self.out_var, width=96).pack(side='left', fill='x', expand=True)
        ttk.Button(row2, text='Save As', style='Primary.TButton', command=self.browse_out).pack(side='left', padx=(8, 0))

        ttk.Label(files, text='ODA File Converter path for DWG input/output').pack(anchor='w')
        row3 = ttk.Frame(files)
        row3.pack(fill='x', pady=(4, 2))
        ttk.Entry(row3, textvariable=self.oda_var, width=96).pack(side='left', fill='x', expand=True)
        ttk.Button(row3, text='Browse', style='Primary.TButton', command=self.browse_oda).pack(side='left', padx=(8, 0))

        opts = section(body, 'Conversion Settings')
        ttk.Label(opts, text='Mode').grid(row=0, column=0, sticky='w')
        ttk.Combobox(opts, textvariable=self.mode_var, values=['State Plane East/West', 'Manual Shift / Rotation / Scale'], state='readonly', width=34).grid(row=0, column=1, sticky='w', padx=(8, 12), pady=(2, 8))
        ttk.Label(opts, text='Source zone').grid(row=1, column=0, sticky='w')
        ttk.Combobox(opts, textvariable=self.source_zone, values=['East', 'West'], state='readonly', width=12).grid(row=1, column=1, sticky='w', padx=(8, 12), pady=(2, 8))
        ttk.Label(opts, text='Target zone').grid(row=1, column=2, sticky='w')
        ttk.Combobox(opts, textvariable=self.target_zone, values=['East', 'West'], state='readonly', width=12).grid(row=1, column=3, sticky='w', padx=(8, 12), pady=(2, 8))

        self.dx_var = tk.StringVar(value='0.0')
        self.dy_var = tk.StringVar(value='0.0')
        self.scale_var = tk.StringVar(value='1.0')
        self.rot_var = tk.StringVar(value='0.0')
        ttk.Label(opts, text='Shift X').grid(row=2, column=0, sticky='w')
        ttk.Entry(opts, textvariable=self.dx_var, width=18).grid(row=2, column=1, sticky='w', padx=(8, 12), pady=(2, 8))
        ttk.Label(opts, text='Shift Y').grid(row=2, column=2, sticky='w')
        ttk.Entry(opts, textvariable=self.dy_var, width=18).grid(row=2, column=3, sticky='w', padx=(8, 12), pady=(2, 8))
        ttk.Label(opts, text='Scale factor').grid(row=3, column=0, sticky='w')
        ttk.Entry(opts, textvariable=self.scale_var, width=18).grid(row=3, column=1, sticky='w', padx=(8, 12), pady=(2, 8))
        ttk.Label(opts, text='Rotation degrees').grid(row=3, column=2, sticky='w')
        ttk.Entry(opts, textvariable=self.rot_var, width=18).grid(row=3, column=3, sticky='w', padx=(8, 12), pady=(2, 8))

        notes = section(body, 'What this converter moves')
        set_output(text_box(notes, height=7), 'Entities handled directly include points, lines, polylines, circles, arcs, text, mtext, inserts, and image references.\n\nFor DXF, the suite edits the drawing directly.\nFor DWG, the suite needs ODA File Converter installed so it can convert DWG to DXF, process the drawing, then convert back to DWG.\n\nThe East/West mode uses projection math in Alabama State Plane and returns coordinates in U.S. survey foot.')
        notes.winfo_children()[-1].pack(fill='x', expand=True)

        run_sec = section(body, 'Run Conversion')
        btns = ttk.Frame(run_sec)
        btns.pack(fill='x', pady=(0, 8))
        ttk.Button(btns, text='Convert Drawing', style='Accent.TButton', command=self.convert).pack(side='left')
        ttk.Button(btns, text='Clear', style='Primary.TButton', command=self.clear_all).pack(side='left', padx=(8, 0))
        self.out_box = text_box(run_sec, height=18)
        self.out_box.pack(fill='both', expand=True)
        ttk.Button(run_sec, text='Copy Report', style='Primary.TButton', command=lambda: copy_to_clipboard(self, self.out_box.get('1.0', 'end').strip())).pack(anchor='w', pady=(8, 0))

    def browse_in(self):
        path = filedialog.askopenfilename(filetypes=[('Drawing files', '*.dxf *.dwg'), ('DXF files', '*.dxf'), ('DWG files', '*.dwg')])
        if path:
            self.in_var.set(path)
            if not self.out_var.get().strip():
                p = Path(path)
                self.out_var.set(str(p.with_name(p.stem + '_converted' + p.suffix)))

    def browse_out(self):
        suffix = '.dxf'
        p = self.in_var.get().strip()
        if p:
            suffix = Path(p).suffix.lower() or '.dxf'
        path = filedialog.asksaveasfilename(defaultextension=suffix, filetypes=[('Drawing files', '*.dxf *.dwg'), ('DXF files', '*.dxf'), ('DWG files', '*.dwg')])
        if path:
            self.out_var.set(path)

    def browse_oda(self):
        path = filedialog.askopenfilename(filetypes=[('ODA File Converter', '*.exe'), ('Executable files', '*.exe')])
        if path:
            self.oda_var.set(path)

    def clear_all(self):
        self.in_var.set('')
        self.out_var.set('')
        self.oda_var.set('')
        self.mode_var.set('State Plane East/West')
        self.source_zone.set('East')
        self.target_zone.set('West')
        self.dx_var.set('0.0')
        self.dy_var.set('0.0')
        self.scale_var.set('1.0')
        self.rot_var.set('0.0')
        self.out_box.delete('1.0', 'end')

    def convert(self):
        try:
            in_path = self.in_var.get().strip()
            out_path = self.out_var.get().strip()
            if not in_path:
                raise RuntimeError('Select an input drawing first.')
            if not out_path:
                raise RuntimeError('Set an output drawing path first.')
            ext_in = Path(in_path).suffix.lower()
            ext_out = Path(out_path).suffix.lower()
            work_in = in_path
            cleanup = []
            oda = None
            if ext_in == '.dwg' or ext_out == '.dwg':
                oda = get_oda_executable(self.oda_var.get().strip())
                if oda is None:
                    raise RuntimeError('DWG conversion needs ODA File Converter installed. Set its EXE path or convert the file to DXF first.')
            if ext_in == '.dwg':
                work_in, temp1, temp2 = dwg_to_dxf_via_oda(in_path, oda)
                cleanup.extend([temp1, temp2])
            work_out = out_path
            if ext_out == '.dwg':
                work_out = str(Path(tempfile.mkdtemp(prefix='schoel_out_dxf_')) / (Path(out_path).stem + '.dxf'))
                cleanup.append(str(Path(work_out).parent))
            count, skipped = process_dxf(
                work_in,
                work_out,
                self.mode_var.get(),
                self.source_zone.get(),
                self.target_zone.get(),
                clean_num(self.dx_var.get(), 0.0),
                clean_num(self.dy_var.get(), 0.0),
                clean_num(self.scale_var.get(), 1.0),
                clean_num(self.rot_var.get(), 0.0),
            )
            if ext_out == '.dwg':
                _, temp3, temp4 = dxf_to_dwg_via_oda(work_out, oda, out_path)
                cleanup.extend([temp3, temp4])
            lines = []
            lines.append(f'Input: {in_path}')
            lines.append(f'Output: {out_path}')
            lines.append(f'Mode: {self.mode_var.get()}')
            if self.mode_var.get() == 'State Plane East/West':
                lines.append(f'Source zone: Alabama {self.source_zone.get()} U.S. survey foot')
                lines.append(f'Target zone: Alabama {self.target_zone.get()} U.S. survey foot')
            else:
                lines.append(f'Shift X: {self.dx_var.get()}')
                lines.append(f'Shift Y: {self.dy_var.get()}')
                lines.append(f'Scale factor: {self.scale_var.get()}')
                lines.append(f'Rotation degrees: {self.rot_var.get()}')
            lines.append(f'Entities changed: {count}')
            if skipped:
                lines.append('')
                lines.append('Entities skipped or unchanged')
                for k, v in sorted(skipped.items()):
                    lines.append(f'- {k}: {v}')
            set_output(self.out_box, '\n'.join(lines))
            for p in cleanup:
                shutil.rmtree(p, ignore_errors=True)
        except subprocess.CalledProcessError as exc:
            msg = exc.stderr.decode(errors='ignore') if getattr(exc, 'stderr', None) else str(exc)
            messagebox.showerror(TITLE, f'ODA File Converter failed.\n\n{msg}')
        except Exception as exc:
            messagebox.showerror(TITLE, str(exc))


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()

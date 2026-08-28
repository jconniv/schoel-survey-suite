import tkinter as tk
from tkinter import ttk, messagebox

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard
from geometry_utils import USFT_PER_M

TITLE = 'Coordinate Converter'

try:
    from pyproj import Transformer
except Exception:
    Transformer = None


EAST_M = 'EPSG:26929'
WEST_M = 'EPSG:26930'
WGS84 = 'EPSG:4326'


def zone_crs(zone: str):
    return EAST_M if zone == 'East' else WEST_M


def main():
    root = tk.Tk()
    root.title(build_title(TITLE))
    root.geometry('980x760')
    apply_theme(root)
    body = make_scrolled_body(root)
    make_header(body, TITLE, 'Convert WGS84 latitude and longitude to Alabama State Plane East or West and back. Output includes meters and U.S. survey feet.')

    note = section(body, 'Projection Note')
    ttk.Label(note, text='Uses NAD83 Alabama East EPSG:26929 and Alabama West EPSG:26930 in meters, then converts to U.S. survey feet.', wraplength=820).pack(anchor='w')

    fwd = section(body, 'Lat/Long to State Plane')
    zone = tk.StringVar(value='East')
    ttk.Combobox(fwd, values=['East', 'West'], textvariable=zone, state='readonly', width=12).pack(anchor='w', pady=6)
    lat_ent = ttk.Entry(fwd, width=24)
    lon_ent = ttk.Entry(fwd, width=24)
    ttk.Label(fwd, text='Latitude').pack(anchor='w')
    lat_ent.pack(anchor='w', pady=(0, 6))
    ttk.Label(fwd, text='Longitude').pack(anchor='w')
    lon_ent.pack(anchor='w', pady=(0, 6))
    out1 = text_box(fwd, height=8)
    out1.pack(fill='x')

    def convert_forward():
        if Transformer is None:
            raise RuntimeError('pyproj is not installed. Run pip install pyproj before building the suite.')
        tr = Transformer.from_crs(WGS84, zone_crs(zone.get()), always_xy=True)
        east_m, north_m = tr.transform(float(lon_ent.get()), float(lat_ent.get()))
        set_output(out1, f'Zone: Alabama {zone.get()}\nNorthing meters: {north_m:,.4f}\nEasting meters: {east_m:,.4f}\nNorthing US survey foot: {north_m * USFT_PER_M:,.4f}\nEasting US survey foot: {east_m * USFT_PER_M:,.4f}')

    ttk.Button(fwd, text='Convert to State Plane', style='Primary.TButton', command=lambda: _safe(convert_forward)).pack(anchor='w', pady=6)

    rev = section(body, 'State Plane to Lat/Long')
    zone2 = tk.StringVar(value='East')
    unit = tk.StringVar(value='US survey foot')
    ttk.Combobox(rev, values=['East', 'West'], textvariable=zone2, state='readonly', width=12).pack(anchor='w', pady=6)
    ttk.Combobox(rev, values=['US survey foot', 'meters'], textvariable=unit, state='readonly', width=18).pack(anchor='w', pady=6)
    north_ent = ttk.Entry(rev, width=24)
    east_ent = ttk.Entry(rev, width=24)
    ttk.Label(rev, text='Northing').pack(anchor='w')
    north_ent.pack(anchor='w', pady=(0, 6))
    ttk.Label(rev, text='Easting').pack(anchor='w')
    east_ent.pack(anchor='w', pady=(0, 6))
    out2 = text_box(rev, height=8)
    out2.pack(fill='x')

    def convert_reverse():
        if Transformer is None:
            raise RuntimeError('pyproj is not installed. Run pip install pyproj before building the suite.')
        n = float(north_ent.get())
        e = float(east_ent.get())
        if unit.get() == 'US survey foot':
            n /= USFT_PER_M
            e /= USFT_PER_M
        tr = Transformer.from_crs(zone_crs(zone2.get()), WGS84, always_xy=True)
        lon, lat = tr.transform(e, n)
        set_output(out2, f'Latitude: {lat:.10f}\nLongitude: {lon:.10f}')

    ttk.Button(rev, text='Convert to Lat/Long', style='Primary.TButton', command=lambda: _safe(convert_reverse)).pack(anchor='w', pady=6)
    ttk.Button(rev, text='Copy Result', style='Accent.TButton', command=lambda: copy_to_clipboard(root, out2.get('1.0', 'end').strip())).pack(anchor='w')
    root.mainloop()


def _safe(fn):
    try:
        fn()
    except Exception as exc:
        messagebox.showerror(TITLE, str(exc))


if __name__ == '__main__':
    main()

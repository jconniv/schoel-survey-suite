import tkinter as tk
from tkinter import ttk, messagebox

from ui_common import build_title, apply_theme, make_scrolled_body, make_header, section, text_box, set_output, copy_to_clipboard
from geometry_utils import parse_bearing, azimuth_to_bearing

TITLE = 'Bearing and Interior Angle Converter'


def main():
    root = tk.Tk()
    root.title(build_title(TITLE))
    root.geometry('980x760')
    apply_theme(root)
    body = make_scrolled_body(root)
    make_header(body, TITLE, 'Convert between bearings and azimuths, and compute the interior angle between two calls. Compact bearings like N451005E are supported.')

    s1 = section(body, 'Bearing to Azimuth')
    bearing_ent = ttk.Entry(s1, width=40)
    bearing_ent.pack(anchor='w', pady=6)
    out1 = text_box(s1, height=4)
    out1.pack(fill='x')
    help_box = text_box(s1, height=5)
    help_box.pack(fill='x', pady=(0,6))
    set_output(help_box, "Examples:\nN45E = North 45° East\nN4510E = North 45°10' East\nN451005E = North 45°10'05\" East")

    def bearing_to_az():
        az = parse_bearing(bearing_ent.get())
        set_output(out1, f'Azimuth: {az:.6f}°')

    ttk.Button(s1, text='Convert Bearing', style='Primary.TButton', command=bearing_to_az).pack(anchor='w', pady=6)

    s2 = section(body, 'Azimuth to Bearing')
    az_ent = ttk.Entry(s2, width=20)
    az_ent.pack(anchor='w', pady=6)
    out2 = text_box(s2, height=4)
    out2.pack(fill='x')

    def az_to_bearing():
        az = float(az_ent.get())
        set_output(out2, azimuth_to_bearing(az))

    ttk.Button(s2, text='Convert Azimuth', style='Primary.TButton', command=az_to_bearing).pack(anchor='w', pady=6)

    s3 = section(body, 'Interior Angle from Two Bearings')
    ttk.Label(s3, text='Previous line bearing').pack(anchor='w')
    prev_ent = ttk.Entry(s3, width=40)
    prev_ent.pack(anchor='w', pady=(0, 6))
    ttk.Label(s3, text='Next line bearing').pack(anchor='w')
    next_ent = ttk.Entry(s3, width=40)
    next_ent.pack(anchor='w', pady=(0, 6))
    out3 = text_box(s3, height=6)
    out3.pack(fill='x')

    def calc_angle():
        az1 = parse_bearing(prev_ent.get())
        az2 = parse_bearing(next_ent.get())
        back = (az1 + 180) % 360
        interior = (az2 - back) % 360
        set_output(out3, f'Back bearing azimuth: {back:.6f}°\nInterior angle turning right: {interior:.6f}°\nInterior angle turning left: {(360 - interior):.6f}°')

    btns = ttk.Frame(s3)
    btns.pack(fill='x', pady=6)
    ttk.Button(btns, text='Compute Interior Angle', style='Primary.TButton', command=calc_angle).pack(side='left')
    ttk.Button(btns, text='Copy Result', style='Accent.TButton', command=lambda: copy_to_clipboard(root, out3.get('1.0', 'end').strip())).pack(side='left', padx=6)
    root.mainloop()


if __name__ == '__main__':
    main()

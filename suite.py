import os
import sys
import json
import re
import shutil
import subprocess
import importlib.util
import types
import traceback
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import ttk, messagebox

APP_TITLE = 'Schoel Survey Suite'
BUILD_NUMBER = '2026.03.27.23'
CACHE_FOLDER_NAME = 'SchoelSurveySuite'
COLORS = {
    'bg': '#f2f3ee',
    'card': '#ffffff',
    'line': '#d8ddca',
    'primary': '#939f4b',
    'primary_dark': '#747f39',
    'accent': '#f47721',
    'accent_dark': '#c85f18',
    'text': '#111111',
    'muted': '#5f6258',
    'button_text': '#ffffff',
}
PLOTTER_WARNING = (
    'Warning\n\n'
    'This deed plotting tool is for internal drafting and review use. '
    'You must independently verify all geometry, closure, bearings, distances, curves, and final survey deliverables before relying on any output.\n\n'
    'Do you want to continue?'
)


def resource_path(rel_path: str) -> str:
    base = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)


def app_dir_path(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        installed_path = os.path.join(exe_dir, filename)
        if os.path.exists(installed_path):
            return installed_path
    return resource_path(filename)


def parse_version(version: str):
    parts = re.findall(r'\d+', str(version))
    return tuple(int(part) for part in parts[:4]) if parts else (0,)


def read_json_source(src: str):
    if re.match(r'^https?://', src, re.I):
        with urllib.request.urlopen(src, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    with open(src, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def resolve_update_path(manifest_src: str, update_path: str) -> str:
    if not update_path:
        return ''
    if re.match(r'^https?://', update_path, re.I) or os.path.isabs(update_path):
        return update_path
    if re.match(r'^https?://', manifest_src, re.I):
        return manifest_src.rsplit('/', 1)[0] + '/' + update_path.replace('\\', '/')
    return os.path.abspath(os.path.join(os.path.dirname(manifest_src), update_path))


def load_local_version() -> str:
    try:
        with open(app_dir_path('version.json'), 'r', encoding='utf-8') as handle:
            return str(json.load(handle).get('version', BUILD_NUMBER)).strip()
    except Exception:
        return BUILD_NUMBER


def load_update_config():
    try:
        with open(app_dir_path('update_config.json'), 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return {'enabled': False, 'manifest': ''}


def check_for_updates(root: tk.Misc) -> None:
    try:
        cfg = load_update_config()
        if not cfg.get('enabled', False):
            return
        manifest_src = str(cfg.get('manifest', '')).strip()
        if not manifest_src:
            return
        manifest = read_json_source(manifest_src)
        current = load_local_version()
        latest = str(manifest.get('version', '')).strip()
        if not latest or parse_version(latest) <= parse_version(current):
            return
        msi = resolve_update_path(manifest_src, str(manifest.get('msi', '')).strip())
        notes = str(manifest.get('notes', '')).strip()
        msg = f'A newer version of {APP_TITLE} is available.\n\nInstalled: {current}\nAvailable: {latest}'
        if notes:
            msg += f'\n\n{notes}'
        msg += '\n\nOpen the installer now?'
        if msi and messagebox.askyesno(f'{APP_TITLE} Update', msg, parent=root):
            if re.match(r'^https?://', msi, re.I):
                webbrowser.open(msi)
            else:
                os.startfile(msi)
    except Exception:
        pass


def user_cache_dir() -> str:
    root = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(root, CACHE_FOLDER_NAME)


def apply_theme(root: tk.Misc):
    root.configure(bg=COLORS['bg'])
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    style.configure('.', font=('Segoe UI', 10))
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'])
    style.configure('Shell.TFrame', background=COLORS['bg'])
    style.configure('Surface.TFrame', background=COLORS['card'], relief='solid', borderwidth=1)
    style.configure('Header.TLabel', background=COLORS['bg'], foreground=COLORS['text'], font=('Segoe UI', 24, 'bold'))
    style.configure('SubHeader.TLabel', background=COLORS['bg'], foreground=COLORS['muted'], font=('Segoe UI', 10))
    style.configure('SectionTitle.TLabel', background=COLORS['card'], foreground=COLORS['text'], font=('Segoe UI', 12, 'bold'))
    style.configure('Footer.TLabel', background=COLORS['bg'], foreground=COLORS['muted'], font=('Segoe UI', 9))
    style.configure('Primary.TButton', padding=(14, 9), font=('Segoe UI', 10, 'bold'))
    style.configure('Accent.TButton', padding=(14, 9), font=('Segoe UI', 10, 'bold'))
    style.map(
        'Primary.TButton',
        background=[('active', COLORS['primary_dark']), ('!disabled', COLORS['primary'])],
        foreground=[('!disabled', COLORS['button_text'])]
    )
    style.map(
        'Accent.TButton',
        background=[('active', COLORS['accent_dark']), ('!disabled', COLORS['accent'])],
        foreground=[('!disabled', COLORS['button_text'])]
    )
    return style


def ask_plotter_warning(title: str) -> bool:
    return messagebox.askokcancel(title, PLOTTER_WARNING, icon='warning')


def load_and_run_file(folder_rel: str, filename: str, friendly_name: str) -> None:
    try:
        folder = resource_path(folder_rel)
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f'{friendly_name} entry file was not found:\n{path}')

        # Ensure the target folder wins import resolution for helper modules like dxf_to_calls.py
        if folder in sys.path:
            sys.path.remove(folder)
        sys.path.insert(0, folder)

        tools_folder = resource_path('tools')
        if tools_folder in sys.path:
            sys.path.remove(tools_folder)
        sys.path.insert(1, tools_folder)

        # Clear common helper modules so one legal writer does not accidentally reuse
        # the other writer's dxf_to_calls or other sibling modules.
        for helper_name in [
            'dxf_to_calls', 'docx_writer', 'rtf_output', 'ui_common', 'build_info'
        ]:
            sys.modules.pop(helper_name, None)

        # Load each tool under an isolated package name.  This prevents the
        # all-in-one PyInstaller build from mixing helper files that share names
        # like dxf_to_calls.py between the Bearing and Interior Angle writers.
        safe_folder = folder_rel.replace('\\', '_').replace('/', '_').replace('-', '_')
        package_name = f"_schoel_runtime_{safe_folder}"
        module_base = os.path.splitext(os.path.basename(filename))[0]
        module_name = f"{package_name}.{module_base}"

        for key in list(sys.modules.keys()):
            if key == package_name or key.startswith(package_name + '.'):
                sys.modules.pop(key, None)

        pkg = types.ModuleType(package_name)
        pkg.__path__ = [folder]  # type: ignore[attr-defined]
        pkg.__file__ = os.path.join(folder, '__init__.py')
        sys.modules[package_name] = pkg

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Could not load {friendly_name} from {path}')
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = package_name
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

        if hasattr(mod, 'App'):
            app = mod.App()
            if hasattr(app, 'mainloop'):
                app.mainloop()
                return
        if hasattr(mod, 'run'):
            mod.run()
            return
        if hasattr(mod, 'main'):
            mod.main()
            return
        raise RuntimeError(f'Could not start {friendly_name}. Expected App, run(), or main().')
    except Exception as e:
        detail = traceback.format_exc()
        messagebox.showerror(friendly_name, f'{e}\n\n{detail}')


def launch_self_flag(flag: str, friendly_name: str) -> None:
    try:
        if getattr(sys, 'frozen', False):
            exe = sys.executable
            cwd = os.path.dirname(exe)
            subprocess.Popen([exe, flag], cwd=cwd)
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), flag], cwd=os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        messagebox.showerror(friendly_name, str(e))


def ensure_bearing_deed_plotter_cached() -> str:
    src_root = resource_path(os.path.join('embedded_deed_plotter', 'Schoel Deed Plotter'))
    dst_root = os.path.join(user_cache_dir(), 'Schoel Deed Plotter')
    exe_path = os.path.join(dst_root, 'Schoel Deed Plotter.exe')
    if os.path.exists(exe_path):
        return dst_root
    if not os.path.exists(src_root):
        raise FileNotFoundError('Embedded Bearing Deed Plotter folder was not found inside the suite.')
    os.makedirs(os.path.dirname(dst_root), exist_ok=True)
    if os.path.exists(dst_root):
        shutil.rmtree(dst_root, ignore_errors=True)
    shutil.copytree(src_root, dst_root)
    return dst_root


def launch_bearing_deed_plotter() -> None:
    if not ask_plotter_warning('Bearing Deed Plotter'):
        return
    try:
        folder = ensure_bearing_deed_plotter_cached()
        exe = os.path.join(folder, 'Schoel Deed Plotter.exe')
        if not os.path.exists(exe):
            raise FileNotFoundError('Could not find the Bearing Deed Plotter EXE after caching.')
        subprocess.Popen([exe], cwd=folder)
    except Exception as e:
        messagebox.showerror('Bearing Deed Plotter', str(e))


def launch_bearing_legal_writer() -> None:
    """Launch the Bearing Legal Writer as its own EXE.

    This keeps it isolated from the Birmingham Interior Angle writer. The two
    writers have helper files with the same names, so running either writer
    inside the all-in-one process can make the CW/CCW logic get crossed up.
    """
    try:
        candidates = []
        if getattr(sys, 'frozen', False):
            candidates.append(resource_path(os.path.join('bearing_writer_exe', 'SchoelLegalDescriptionGenerator.exe')))
            candidates.append(os.path.join(os.path.dirname(sys.executable), 'SchoelLegalDescriptionGenerator.exe'))
        else:
            candidates.append(resource_path(os.path.join('legal_writer_bearing', 'dist', 'SchoelLegalDescriptionGenerator.exe')))
            candidates.append(resource_path(os.path.join('bearing_writer_exe', 'SchoelLegalDescriptionGenerator.exe')))

        for exe_path in candidates:
            if exe_path and os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                return

        # Source-mode fallback only. The built suite should use the EXE above.
        load_and_run_file('legal_writer_bearing', 'app.py', 'Bearing Legal Writer')
    except Exception as e:
        messagebox.showerror('Bearing Legal Writer', str(e))



def launch_angle_legal_writer() -> None:
    """Launch the Birmingham Interior Angle writer as its own EXE.

    This is intentional. The standalone Birmingham writer is the version that
    proved the CW/CCW toggle works. Running it as a separate process prevents
    the all-in-one suite from reusing/mixing helper modules that have the same
    names in the bearing writer and angle writer folders.
    """
    try:
        candidates = []
        if getattr(sys, 'frozen', False):
            candidates.append(resource_path(os.path.join('angle_writer_exe', 'BirminghamLegalDescriptionWriter.exe')))
            candidates.append(os.path.join(os.path.dirname(sys.executable), 'BirminghamLegalDescriptionWriter.exe'))
        else:
            candidates.append(resource_path(os.path.join('legal_writer_angle', 'dist', 'BirminghamLegalDescriptionWriter.exe')))
            candidates.append(resource_path(os.path.join('angle_writer_exe', 'BirminghamLegalDescriptionWriter.exe')))

        for exe_path in candidates:
            if exe_path and os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                return

        # Source-mode fallback only.  The built suite should never use this.
        load_and_run_file('legal_writer_angle', 'app.py', 'Interior Angle Legal Writer')
    except Exception as e:
        messagebox.showerror('Interior Angle Legal Writer', str(e))


def launch_angle_deed_plotter() -> None:
    if not ask_plotter_warning('Interior Angle Deed Plotter'):
        return
    launch_self_flag('--angle-plotter', 'Interior Angle Deed Plotter')


def launch_tool(module_name: str, friendly_name: str) -> None:
    launch_self_flag(f'--tool={module_name}', friendly_name)


def open_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    os.startfile(path)  # type: ignore[attr-defined]


def open_suite_cache_folder() -> None:
    try:
        open_folder(user_cache_dir())
    except Exception as e:
        messagebox.showerror('Open folder', str(e))


def open_assets_folder() -> None:
    try:
        open_folder(resource_path('assets'))
    except Exception as e:
        messagebox.showerror('Assets folder', str(e))


def add_section(parent, title: str):
    frame = ttk.Frame(parent, style='Surface.TFrame', padding=(14, 12))
    frame.pack(fill='x', pady=8)
    ttk.Label(frame, text=title, style='SectionTitle.TLabel').pack(anchor='w', pady=(0, 8))
    return frame


def add_button(parent, text: str, cmd, accent=False) -> None:
    style = 'Accent.TButton' if accent else 'Primary.TButton'
    ttk.Button(parent, text=text, command=cmd, style=style).pack(fill='x', pady=4, ipady=2)


def add_button_grid(parent, items, columns: int = 2) -> None:
    grid = ttk.Frame(parent, style='Surface.TFrame')
    grid.pack(fill='x')
    for col in range(columns):
        grid.columnconfigure(col, weight=1, uniform='actions')
    for idx, (text, cmd, accent) in enumerate(items):
        row = idx // columns
        col = idx % columns
        style = 'Accent.TButton' if accent else 'Primary.TButton'
        ttk.Button(grid, text=text, command=cmd, style=style).grid(
            row=row,
            column=col,
            sticky='ew',
            padx=(0 if col == 0 else 6, 0 if col == columns - 1 else 6),
            pady=5,
            ipady=2,
        )


def logo_label(parent):
    try:
        path = resource_path(os.path.join('assets', 'schoel_logo.png'))
        if os.path.exists(path):
            img = tk.PhotoImage(file=path)
            try:
                img = img.subsample(max(1, img.width() // 280), max(1, img.height() // 80))
            except Exception:
                pass
            lbl = tk.Label(parent, image=img, bg=COLORS['bg'])
            lbl.image = img
            lbl.pack(anchor='w', pady=(0, 10))
    except Exception:
        pass


def suite_ui() -> None:
    root = tk.Tk()
    root.title(f'{APP_TITLE} | Build {BUILD_NUMBER}')
    root.geometry('980x780')
    root.minsize(900, 700)

    try:
        icon_path = resource_path(os.path.join('assets', 'schoel_logo.ico'))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    apply_theme(root)

    canvas = tk.Canvas(root, highlightthickness=0, bg=COLORS['bg'])
    scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    container = ttk.Frame(canvas, style='Shell.TFrame')
    container.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    window_id = canvas.create_window((0, 0), window=container, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    def _fit_container(event):
        canvas.itemconfigure(window_id, width=event.width)

    canvas.bind('<Configure>', _fit_container)

    outer = ttk.Frame(container, style='Shell.TFrame', padding=(24, 20))
    outer.pack(fill='both', expand=True)

    header = ttk.Frame(outer, style='Shell.TFrame')
    header.pack(fill='x', pady=(0, 14))

    logo_wrap = ttk.Frame(header, style='Shell.TFrame')
    logo_wrap.pack(side='left', fill='y', padx=(0, 18))
    logo_label(logo_wrap)

    title_wrap = ttk.Frame(header, style='Shell.TFrame')
    title_wrap.pack(side='left', fill='both', expand=True)
    ttk.Label(title_wrap, text='Schoel Survey Suite', style='Header.TLabel').pack(anchor='w')
    ttk.Label(
        title_wrap,
        text=f'Build {BUILD_NUMBER} | Survey production tools',
        style='SubHeader.TLabel',
        wraplength=760,
        justify='left'
    ).pack(anchor='w', pady=(4, 0))

    band = tk.Frame(outer, bg=COLORS['primary'], height=4)
    band.pack(fill='x', pady=(0, 4))
    accent_band = tk.Frame(outer, bg=COLORS['accent'], height=2)
    accent_band.pack(fill='x', pady=(0, 14))

    core = add_section(outer, 'Core Tools')
    add_button_grid(core, [
        ('Bearing Deed Plotter', launch_bearing_deed_plotter, False),
        ('Interior Angle Deed Plotter', launch_angle_deed_plotter, False),
        ('Bearing Legal Writer', launch_bearing_legal_writer, False),
        ('Interior Angle Legal Writer', launch_angle_legal_writer, False),
        ('Teach Parser', lambda: launch_tool('teach_parser', 'Teach Parser'), True),
    ])

    qa = add_section(outer, 'Geometry and QA')
    add_button_grid(qa, [
        ('Curve Table Generator', lambda: launch_tool('curve_table', 'Curve Table Generator'), False),
        ('Bearing and Angle Converter', lambda: launch_tool('bearing_angle_converter', 'Bearing and Interior Angle Converter'), False),
        ('Drawing Zone Converter', lambda: launch_tool('drawing_zone_converter', 'Drawing Zone Converter'), True),
    ])

    util = add_section(outer, 'Survey Utilities')
    add_button_grid(util, [
        ('Coordinate Converter', lambda: launch_tool('coordinate_converter', 'Coordinate Converter'), False),
        ('Survey Foot/Inch Converter', lambda: launch_tool('survey_foot_inch_converter', 'Survey Foot to Inch Converter'), False),
        ('PLSS Deed Locator', lambda: launch_tool('plss_deed_locator', 'PLSS Deed Locator'), True),
        ('PLSS Angle Deed Locator', lambda: launch_tool('plss_angle_deed_locator', 'PLSS Angle Deed Locator'), True),
        ('AI Closure Assistant', lambda: launch_tool('ai_helper', 'AI Closure Assistant'), True),
    ])

    ttk.Label(outer, text=f'Build {BUILD_NUMBER}', style='Footer.TLabel').pack(anchor='e', pady=(4, 0))

    support = add_section(outer, 'Support')
    add_button(support, 'Open Suite Cache Folder', open_suite_cache_folder)
    add_button(support, 'Open Assets Folder', open_assets_folder)

    ttk.Label(
        outer,
        text='Use outputs for drafting and review only. Verify geometry before relying on final deliverables.',
        style='Footer.TLabel',
        wraplength=860,
        justify='left'
    ).pack(anchor='w', pady=(8, 0))


    def _on_mousewheel(event):
        try:
            widget = root.focus_get()
            if widget and widget.winfo_class() in {'Text', 'Entry', 'TEntry'}:
                return
        except Exception:
            pass
        canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    canvas.bind_all('<MouseWheel>', _on_mousewheel)
    root.after(800, lambda: check_for_updates(root))
    root.mainloop()


def bearing_legal_mode() -> None:
    load_and_run_file('legal_writer_bearing', 'app.py', 'Bearing Legal Writer')


def angle_legal_mode() -> None:
    launch_angle_legal_writer()


def angle_plotter_mode() -> None:
    load_and_run_file('plotter_angle', 'app.py', 'Interior Angle Deed Plotter')


def tool_mode(name: str) -> None:
    load_and_run_file('tools', f'{name}.py', name)


if __name__ == '__main__':
    if '--bearing-legal' in sys.argv:
        bearing_legal_mode()
    elif '--angle-legal' in sys.argv:
        angle_legal_mode()
    elif '--angle-plotter' in sys.argv:
        angle_plotter_mode()
    else:
        tool_flag = next((arg for arg in sys.argv if arg.startswith('--tool=')), None)
        if tool_flag:
            tool_mode(tool_flag.split('=', 1)[1])
        else:
            suite_ui()

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['suite.py'],
    pathex=['legal_writer_bearing', 'legal_writer_angle', 'plotter_angle', 'tools'],
    binaries=[
        ('legal_writer_angle\\dist\\BirminghamLegalDescriptionWriter.exe', 'angle_writer_exe'),
        ('legal_writer_bearing\\dist\\SchoelLegalDescriptionGenerator.exe', 'bearing_writer_exe'),
    ],
    datas=[
        ('version.json', '.'),
        ('update_config.json', '.'),
        ('assets', 'assets'),
        ('embedded_deed_plotter', 'embedded_deed_plotter'),
        ('legal_writer_bearing', 'legal_writer_bearing'),
        ('legal_writer_angle', 'legal_writer_angle'),
        ('plotter_angle', 'plotter_angle'),
        ('tools', 'tools'),
    ],
    hiddenimports=[
        'tkinter', 'tkinter.filedialog', 'tkinter.messagebox', 'tkinter.ttk',
        'comtypes', 'comtypes.client',
        'ezdxf',
        'parser_deed', 'traverse', 'plotter', 'dxf_writer',
        'matplotlib', 'matplotlib.backends.backend_tkagg', 'matplotlib.figure', 'pyproj'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SchoelSurveySuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon='assets\\schoel_logo.ico',
)

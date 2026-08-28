import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "version.json"
VERSION_INFO = ROOT / "version_info.txt"


def read_version():
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    return data["name"], data["version"]


def write_version(name, version):
    VERSION_FILE.write_text(json.dumps({"name": name, "version": version}, indent=2) + "\n", encoding="utf-8")


def bump_patch(version):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        raise SystemExit(f"Version must be major.minor.patch, got {version}")
    major, minor, patch = map(int, m.groups())
    return f"{major}.{minor}.{patch + 1}"


def write_version_info(name, version):
    major, minor, patch = map(int, version.split("."))
    VERSION_INFO.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Schoel Engineering'),
      StringStruct('FileDescription', '{name}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'SchoelSurveySuite'),
      StringStruct('OriginalFilename', 'SchoelSurveySuite.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")


def main():
    name, current = read_version()
    version = sys.argv[1] if len(sys.argv) > 1 else bump_patch(current)
    write_version(name, version)
    write_version_info(name, version)
    temp_root = Path(tempfile.gettempdir()) / "SchoelSurveySuiteRelease"
    dist_dir = temp_root / "dist"
    work_dir = temp_root / "build"
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    exe_path = dist_dir / "SchoelSurveySuite.exe"
    if exe_path.exists():
        try:
            os.chmod(exe_path, 0o666)
            exe_path.unlink()
        except OSError as exc:
            raise SystemExit(f"Could not remove existing {exe_path}. Close Schoel Survey Suite and try again. {exc}")
    subprocess.check_call([
        sys.executable,
        "-m",
        "PyInstaller",
        "SchoelSurveySuite.spec",
        "--noconfirm",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
    ], cwd=ROOT)
    if os.environ.get("SCHOEL_SKIP_SIGNING") != "1":
        subprocess.check_call([
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "Sign-Programs.ps1"),
            "-Path",
            str(exe_path),
        ], cwd=ROOT)
    (ROOT / "release_exe_path.txt").write_text(str(exe_path) + "\n", encoding="utf-8")
    print(f"Built {name} v{version}")


if __name__ == "__main__":
    main()

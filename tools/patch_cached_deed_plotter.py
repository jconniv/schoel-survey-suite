import argparse
import marshal
import os
import shutil
import tempfile
import time
import types
import zlib

from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader


DEFAULT_EXE = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "SchoelSurveySuite",
    "Schoel Deed Plotter",
    "Schoel Deed Plotter.exe",
)

MODULE_NAME = "schoel_deed_plotter.dxf_io"
OLD_SKIP_LENGTH = 30.0
NEW_SKIP_LENGTH = 0.0


def _replace_short_label_cutoff(code):
    changed = 0
    new_consts = []

    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            patched, nested_changed = _replace_short_label_cutoff(const)
            new_consts.append(patched)
            changed += nested_changed
        elif code.co_name == "export_dxf" and const == OLD_SKIP_LENGTH:
            new_consts.append(NEW_SKIP_LENGTH)
            changed += 1
        else:
            new_consts.append(const)

    if changed:
        return code.replace(co_consts=tuple(new_consts)), changed
    return code, changed


def patch_exe(exe_path, dry_run=False):
    exe_path = os.path.abspath(exe_path)
    if not os.path.exists(exe_path):
        raise FileNotFoundError(exe_path)

    carchive = CArchiveReader(exe_path)
    pyz_entry = carchive.toc.get("PYZ.pyz")
    if pyz_entry is None:
        raise RuntimeError("Could not find PYZ.pyz inside the plotter EXE.")

    pyz_entry_offset, _pyz_len, _pyz_uncompressed_len, pyz_compressed, _typecode = pyz_entry
    if pyz_compressed:
        raise RuntimeError("Unexpected compressed PYZ entry; refusing to patch in place.")

    pyz_bytes = carchive.extract("PYZ.pyz")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pyz") as tmp:
        tmp.write(pyz_bytes)
        tmp_path = tmp.name

    try:
        zarchive = ZlibArchiveReader(tmp_path)
        module_entry = zarchive.toc.get(MODULE_NAME)
        if module_entry is None:
            raise RuntimeError(f"Could not find {MODULE_NAME} inside the plotter EXE.")

        typecode, module_offset, old_entry_len = module_entry
        old_code = zarchive.extract(MODULE_NAME)
        if not isinstance(old_code, types.CodeType):
            raise RuntimeError(f"{MODULE_NAME} did not extract as a code object.")

        new_code, changed = _replace_short_label_cutoff(old_code)
        if changed != 1:
            raise RuntimeError(f"Expected to patch one 30 ft cutoff, patched {changed}.")

        new_entry = zlib.compress(marshal.dumps(new_code))
        if len(new_entry) > old_entry_len:
            raise RuntimeError(
                f"Patched module is {len(new_entry)} bytes but original slot is only "
                f"{old_entry_len} bytes; cannot patch safely in place."
            )

        patch_offset = carchive._start_offset + pyz_entry_offset + module_offset
        backup_path = None

        if not dry_run:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"{exe_path}.pre_short_label_patch_{stamp}.bak"
            shutil.copy2(exe_path, backup_path)
            with open(exe_path, "r+b") as f:
                f.seek(patch_offset)
                f.write(new_entry)
                if len(new_entry) < old_entry_len:
                    f.write(b"\0" * (old_entry_len - len(new_entry)))

        return {
            "exe": exe_path,
            "backup": backup_path,
            "changed": changed,
            "old_entry_len": old_entry_len,
            "new_entry_len": len(new_entry),
            "patch_offset": patch_offset,
            "dry_run": dry_run,
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=DEFAULT_EXE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = patch_exe(args.exe, dry_run=args.dry_run)
    print("Patched cutoff check OK" if args.dry_run else "Patched cached plotter EXE")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pack a KernelSU / Magisk module folder (e.g. modules/thermal-monitor) into an installable ZIP.

The ZIP is reproducible: fixed timestamps, sorted entries, scripts 0755 and everything else 0644.
README files stay out of the ZIP. Prints the path of the ZIP.
Usage: package_module.py MODULE_DIR OUT_DIR
"""
import sys
import zipfile
from pathlib import Path

EXECUTABLE = {"update-binary"}
SKIP = {"README.md", "README.en.md"}


def read_prop(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def package(module, out):
    prop = read_prop(module / "module.prop")
    name = prop["name"].replace(" ", "-")
    target = out / f"{name}-{prop['version']}.zip"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in module.rglob("*") if p.is_file()):
            relative = path.relative_to(module).as_posix()
            if path.name in SKIP or "__pycache__" in relative:
                continue
            info = zipfile.ZipInfo(relative, date_time=(2024, 1, 1, 0, 0, 0))
            mode = 0o755 if path.suffix == ".sh" or path.name in EXECUTABLE else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return target


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[-1])
    print(package(Path(sys.argv[1]), Path(sys.argv[2])))

#!/usr/bin/env python3
"""Prepare the locked v2 source bundle, optionally stage adjacent clean checkouts.

Offline only. No compiler, download, upstream installer, release, or production
build path is invoked. A prepared bundle alone does not authorize compilation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/ksun-susfs-6.1-candidate-v2.json"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def run(command):
    return subprocess.run(command, check=True, capture_output=True,
                          text=True, timeout=60)


def verified_bytes(path, expected):
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise ValueError("SHA256 mismatch: " + str(path))
    return raw


def read_companions(archive, entries):
    """Read only exact locked regular files; never extract ZIP paths."""
    expected = {item["archive_path"]: item for item in entries}
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if len(members) != len(expected) or {m.filename for m in members} != set(expected):
            raise ValueError("ZIP must contain exactly the four locked files")
        result = {}
        for member in members:
            mode = member.external_attr >> 16
            if member.is_dir() or (mode & 0o170000) not in (0, 0o100000):
                raise ValueError("ZIP member is not a regular file")
            if member.file_size > 1024 * 1024:
                raise ValueError("ZIP member exceeds source size limit")
            raw = source.read(member)
            if sha256(raw) != expected[member.filename]["sha256"]:
                raise ValueError("ZIP member SHA256 mismatch: " + member.filename)
            result[member.filename] = raw
    return result


def checkout(path, expected, nonshallow=False):
    path = path.resolve(strict=True)
    top = Path(run(["git", "-C", str(path), "rev-parse", "--show-toplevel"]).stdout.strip())
    if top.resolve() != path:
        raise ValueError("Expected checkout root: " + str(path))
    actual = run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()
    if actual != expected:
        raise ValueError("Checkout HEAD mismatch: " + str(path))
    if run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"]).stdout.strip():
        raise ValueError("Dirty checkout: " + str(path))
    if nonshallow and run(["git", "-C", str(path), "rev-parse", "--is-shallow-repository"]).stdout.strip() != "false":
        raise ValueError("Shallow KSUN checkout could trigger Kbuild's unshallow fetch")
    return path


def staging_inputs(kernel, ksun, lock):
    kernel = checkout(kernel, lock["kernel_commit"])
    ksun = checkout(ksun, lock["ksun_commit"], nonshallow=True)
    if kernel.name != "kernel" or ksun.name != "ksun" or kernel.parent != ksun.parent:
        raise ValueError("Staging requires adjacent directories named kernel and ksun")
    for entry in lock["files"]:
        if "destination" in entry and os.path.lexists(kernel / entry["destination"]):
            raise ValueError("Companion destination already exists: " + entry["destination"])
    if os.path.lexists(kernel / "drivers/kernelsu") or (kernel / ".config").exists():
        raise ValueError("Expected pristine kernel without KSUN link or in-tree .config")
    if not (ksun / "kernel/Kbuild").is_file():
        raise ValueError("KSUN kernel directory is missing")
    return kernel, ksun


def write_bundle(archive, output, lock, kernel=None, ksun=None):
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; refusing overwrite")
    if not output.parent.is_dir():
        raise ValueError("Output parent must already exist")
    if kernel is not None:
        kernel, ksun = staging_inputs(kernel, ksun, lock)
        for source in (kernel, ksun):
            if output.resolve().is_relative_to(source):
                raise ValueError("Bundle output must be outside source checkouts")
    raw_files = read_companions(archive, lock["files"])
    driver = verified_bytes(ROOT / lock["driver_integration"]["path"],
                            lock["driver_integration"]["sha256"])
    historical = json.loads((ROOT / "configs/ksun-susfs-6.1.lock.json").read_text())
    if historical["adaptation"] != lock["adaptation"]:
        raise ValueError("Historical patch adaptation changed; review candidate lock")
    # Preparation writes only a temporary bundle until every input is verified.
    with tempfile.TemporaryDirectory(prefix=".ksun-susfs-v2-", dir=output.parent) as temp:
        bundle = Path(temp) / "bundle"
        (bundle / "patches").mkdir(parents=True)
        original = Path(temp) / "original.patch"
        original.write_bytes(raw_files[lock["original_patch"]])
        prepared = bundle / "patches/002-susfs-prepared.patch"
        run([sys.executable, str(ROOT / "scripts/prepare_susfs_kernel_patch.py"),
             str(original), str(prepared)])
        prepared_raw = verified_bytes(prepared, lock["adaptation"]["output_sha256"])
        (bundle / "patches/001-ksun-driver.patch").write_bytes(driver)
        for entry in lock["files"]:
            if "destination" in entry:
                target = bundle / "companions" / entry["destination"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw_files[entry["archive_path"]])
        manifest = {
            "kernel_commit": lock["kernel_commit"],
            "scope": "minimal KSUN+SUSFS source stage; feature bundle and build gates remain blocked",
            "patches": [
                {"path": "patches/001-ksun-driver.patch", "sha256": sha256(driver)},
                {"path": "patches/002-susfs-prepared.patch", "sha256": sha256(prepared_raw)},
            ],
        }
        (bundle / "kernel-replay.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (bundle / "candidate-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        # mkdir is exclusive; another writer cannot cause an existing output to be replaced.
        output.mkdir()
        for child in bundle.iterdir():
            shutil.move(str(child), output / child.name)
    if kernel is not None:
        # Existing replay first checks the complete ordered series in a disposable index.
        run([sys.executable, str(ROOT / "scripts/ksun_susfs_replay.py"),
             str(kernel), str(output / "kernel-replay.json"), "--apply"])
        for entry in lock["files"]:
            if "destination" in entry:
                target = kernel / entry["destination"]
                with target.open("xb") as stream:
                    stream.write(raw_files[entry["archive_path"]])
                verified_bytes(target, entry["sha256"])
        link = kernel / "drivers/kernelsu"
        if not link.is_symlink() or link.resolve() != ksun / "kernel":
            raise ValueError("KSUN driver symlink target mismatch")
        evidence = {
            "status": "source_staged_not_compilation_ready",
            "kernel_head": lock["kernel_commit"], "ksun_head": lock["ksun_commit"],
            "kernel_diff_sha256": sha256(run(["git", "-C", str(kernel), "diff", "--binary"]).stdout.encode()),
            "kernel_status": run(["git", "-C", str(kernel), "status", "--porcelain", "--untracked-files=all"]).stdout,
            "companions_sha256": {e["destination"]: e["sha256"] for e in lock["files"] if "destination" in e},
            "full_image_verified": False, "runtime_verified": False,
        }
        (output / "stage-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("susfs_zip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--kernel", type=Path, help="Stage only this isolated clean checkout")
    parser.add_argument("--ksun", type=Path, help="Adjacent pinned nonshallow KSUN checkout")
    args = parser.parse_args()
    try:
        if (args.kernel is None) != (args.ksun is None):
            raise ValueError("--kernel and --ksun must be supplied together")
        lock = json.loads(LOCK.read_text())
        write_bundle(args.susfs_zip.resolve(strict=True), args.output.absolute(), lock,
                     args.kernel, args.ksun)
        print("VERIFIED: v2 source bundle prepared" + (" and isolated sources staged" if args.kernel else ""))
        print("NOT COMPILATION READY: toolchain, resolved config, and feature bundle gates remain")
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print("BLOCKED: " + detail[:2000], file=sys.stderr)
        print("Preserve any prepared bundle or staged tree for diagnosis; do not retry blindly.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Offline BBG/NoMount patch preparation for the exact verified core tree.

No installers or compiler are executed. --apply invokes the existing strict
whole-series replay only after every source and generated-patch hash matches.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(kernel, *args):
    return subprocess.run(["git", "-C", str(kernel), *args],
                          check=True, capture_output=True, timeout=60).stdout


def before_endmenu(raw, entry):
    text = raw.decode()
    if entry in text:
        raise ValueError("Integration entry already exists")
    point = text.rfind("\nendmenu")
    if point < 0:
        raise ValueError("Expected final Kconfig endmenu")
    return (text[:point] + "\n" + entry + "\n" + text[point:]).encode()


def changed(path, old, new):
    delta = "".join(difflib.unified_diff(old.decode().splitlines(keepends=True),
                    new.decode().splitlines(keepends=True),
                    fromfile="a/" + path, tofile="b/" + path))
    if not delta:
        raise ValueError("Empty patch: " + path)
    return ("diff --git a/" + path + " b/" + path + "\n" + delta).encode()


def added(path, raw):
    lines = raw.decode().splitlines(keepends=True)
    if not lines:
        raise ValueError("Empty source file: " + path)
    body = "".join("+" + line for line in lines)
    if not raw.endswith(b"\n"):
        body += "\n\\ No newline at end of file\n"
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body).encode()


def verified(root, rel, expected):
    path = root / rel
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root.resolve()):
        raise ValueError("Source path escapes root: " + rel)
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError("Source SHA256 mismatch: " + rel)
    return raw


def generate(kernel, sources, lock):
    inputs = {p: verified(kernel, p, h) for p, h in lock["kernel_inputs_sha256"].items()}
    patches = []
    for feature in lock["features"]:
        name = feature["name"]
        raw_sources = {entry["path"]: verified(sources / name, entry["path"], entry["sha256"])
                       for entry in feature["files"]}
        if name == "bbg":
            mk, kc = "security/Makefile", "security/Kconfig"
            symbol, source_entry = b"obj-$(CONFIG_BBG) += baseband-guard/", 'source "security/baseband-guard/Kconfig"'
        else:
            mk, kc = "fs/Makefile", "fs/Kconfig"
            symbol, source_entry = b"obj-$(CONFIG_NOMOUNT) += nomount/", 'source "fs/nomount/Kconfig"'
        if symbol in inputs[mk]:
            raise ValueError("Makefile entry already exists")
        raw = changed(mk, inputs[mk], inputs[mk].rstrip(b"\n") + b"\n\n" + symbol + b"\n")
        raw += changed(kc, inputs[kc], before_endmenu(inputs[kc], source_entry))
        for entry in feature["files"]:
            content = raw_sources[entry["path"]]
            if entry["path"] == "Makefile" and name == "bbg":
                text = content.decode()
                start = text.index("GIT_BIN :=")
                end = text.index('ifeq ($(shell grep -q "file_ioctl_compat"', start)
                text = text[:start] + ("# Offline identity for the exact locked BBG source.\n"
                       "REPO_LINK := https://github.com/vc-teahouse/Baseband-guard\n"
                       "COMMIT_SHA := a54e0dc6\n\n") + text[end:]
                content = text.encode()
            elif entry["path"] == "kernel/src/Makefile" and name == "nomount":
                text = content.decode()
                start, end = text.index("NOMOUNT_COMMITS :="), text.index("obj-$(CONFIG_NOMOUNT)")
                content = (text[:start] + "# Locked source 7046c7ad; use upstream base version 21 without Git queries.\n\n" + text[end:]).encode()
            if "adapted_sha256" in entry and sha(content) != entry["adapted_sha256"]:
                raise ValueError("Adapted Makefile SHA256 mismatch")
            if (kernel / entry["destination"]).exists():
                raise ValueError("Feature destination already exists: " + entry["destination"])
            raw += added(entry["destination"], content)
        patches.append((feature["patch"], raw))
    return patches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("sources", type=Path, help="Directory containing verified bbg/ and nomount/ snapshots")
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        lock = json.loads(LOCK.read_text())
        kernel, sources = args.kernel.resolve(strict=True), args.sources.resolve(strict=True)
        if Path(git(kernel, "rev-parse", "--show-toplevel").decode().strip()).resolve() != kernel:
            raise ValueError("Expected checkout root")
        if git(kernel, "status", "--porcelain", "--untracked-files=all").strip():
            raise ValueError("Expected clean frozen core checkout")
        tree = git(kernel, "rev-parse", "HEAD^{tree}").decode().strip()
        if tree != lock["core_kernel_tree"]:
            raise ValueError("Core source tree mismatch")
        output = args.output.absolute()
        if output.exists() or output.is_symlink() or not output.parent.is_dir():
            raise ValueError("Expected new output path with an existing parent")
        if output.resolve().is_relative_to(kernel):
            raise ValueError("Output must be outside kernel checkout")
        patches = generate(kernel, sources, lock)
        manifest = {"kernel_commit": git(kernel, "rev-parse", "HEAD").decode().strip(),
                    "core_tree": tree,
                    "scope": "BBG, BBG allow-cache locking fix and NoMount continuation only",
                    "patches": []}
        for name, raw in patches:
            if sha(raw) != lock["generated_patches_sha256"][name]:
                raise ValueError("Generated patch SHA256 mismatch: " + name)
            manifest["patches"].append({"path": name, "sha256": sha(raw)})
        # Owner-approved fixes kept as separate, checksummed patches after the generated ones.
        for reviewed in lock.get("reviewed_patches", []):
            raw = (ROOT / reviewed["source"]).read_bytes()
            if sha(raw) != reviewed["sha256"]:
                raise ValueError("Reviewed patch SHA256 mismatch: " + reviewed["name"])
            patches.append((reviewed["name"], raw))
            manifest["patches"].append({"path": reviewed["name"], "sha256": reviewed["sha256"]})
        with tempfile.TemporaryDirectory(prefix=".ksun-features-", dir=output.parent) as temp:
            temp = Path(temp)
            for name, raw in patches:
                (temp / name).write_bytes(raw)
            (temp / "kernel-replay.json").write_text(json.dumps(manifest, indent=2) + "\n")
            output.mkdir()
            for path in temp.iterdir():
                path.rename(output / path.name)
        if args.apply:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/ksun_susfs_replay.py"),
                                     str(kernel), str(output / "kernel-replay.json"), "--apply"],
                                    check=True, capture_output=True, text=True, timeout=120)
            (output / "replay.log").write_text(result.stdout)
            print(result.stdout, end="")
        print("FEATURE SOURCE PREPARED; config/compiler and Image/runtime remain separate gates")
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + (getattr(exc, "stderr", None) or str(exc))[:2000], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

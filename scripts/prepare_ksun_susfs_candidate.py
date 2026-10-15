#!/usr/bin/env python3
"""Prepare the locked v2 source bundle, optionally stage adjacent clean checkouts.

Offline only. No compiler, download, upstream installer, release, or production
build path is invoked. A prepared bundle alone does not authorize compilation.
Use --locked-worktrees KERNEL KSUN NEW_DIRECTORY for the fully locked local
worktree route; the archive-bundle interface remains available unchanged.
"""
import argparse
import difflib
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
                          text=True, timeout=60, env=OFFLINE_ENV)


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
    if sys.argv[1:2] == ["--locked-worktrees"]:
        return prepare_locked_worktrees(sys.argv[2:])
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


WORKTREE_LOCK = ROOT / "configs/ksun-susfs-6.1-v2.lock.json"
OFFLINE_ENV = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0",
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="protocol.allow",
                   GIT_CONFIG_VALUE_0="never")


def offline_run(*args, cwd=None, raw=None):
    return subprocess.run(args, cwd=cwd, input=raw, capture_output=True,
                          check=True, timeout=180, env=OFFLINE_ENV).stdout


def offline_git(tree, *args):
    return offline_run("git", "-C", str(tree), *args).decode().strip()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_checkout(tree, commit):
    tree = tree.resolve(strict=True)
    if not (tree / ".git").exists():
        raise ValueError("source must be a Git checkout/worktree root")
    if Path(offline_git(tree, "rev-parse", "--show-toplevel")).resolve() != tree:
        raise ValueError("source path must be the checkout root")
    if offline_git(tree, "rev-parse", "HEAD") != commit:
        raise ValueError("source HEAD mismatch: " + str(tree))
    if offline_git(tree, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source is dirty: " + str(tree))
    return tree


def verify_files(root, entries):
    """Return exact reviewed bytes; reject symlinks and path escapes."""
    result = {}
    for rel, expected in entries.items():
        path = root / rel
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("input path escapes source root: " + rel)
        raw = path.read_bytes()
        if digest(raw) != expected:
            raise ValueError("SHA256 mismatch: " + rel)
        result[rel] = raw
    return result


def text_patch(path, before, after):
    raw = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/" + path, tofile="b/" + path))
    if not raw:
        raise ValueError("empty integration patch: " + path)
    return ("diff --git a/" + path + " b/" + path + "\n" + raw).encode()


def added_file_patch(path, raw, mode="100644"):
    text = raw.decode("utf-8")
    if "\0" in text or not text.endswith("\n"):
        raise ValueError("companion must be newline-terminated UTF-8: " + path)
    lines = text.splitlines(keepends=True)
    return (f"diff --git a/{path} b/{path}\nnew file mode {mode}\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" +
            "".join("+" + line for line in lines)).encode()


def record_patch(directory, name, raw, source):
    (directory / name).write_bytes(raw)
    return {"path": name, "sha256": digest(raw), "source": source}


def prepare_locked_worktrees(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("ksun", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    output = None
    created = False
    try:
        lock = json.loads(WORKTREE_LOCK.read_text())
        if lock["build_enabled"] is not False or any(lock["guards"].values()):
            raise ValueError("candidate source-only guards must remain false")
        kernel = verify_checkout(args.kernel, lock["sources"]["kernel"]["commit"])
        ksun = verify_checkout(args.ksun, lock["sources"]["ksun"]["commit"])
        reviewed = verify_files(ksun, lock["reviewed_ksun_files_sha256"])
        inputs = verify_files(ROOT, {e["path"]: e["sha256"] for e in lock["inputs"]})
        adaptation = lock["adaptation"]
        verify_files(ROOT, {adaptation["delta"]: adaptation["delta_sha256"]})
        metadata = lock["offline_version"]
        if offline_git(ksun, "rev-parse", "--is-shallow-repository") != "false":
            raise ValueError("complete local KSUN history required; no automatic fetch")
        if offline_git(ksun, "rev-parse", "refs/tags/" + metadata["tag"] + "^{commit}") != metadata["tag_commit"]:
            raise ValueError("KSUN version tag mismatch")
        if (int(offline_git(ksun, "rev-list", "--count", "HEAD")) != metadata["head_revision_count"]
                or offline_git(ksun, "describe", "--tags", "--abbrev=0", "HEAD") != metadata["tag"]):
            raise ValueError("KSUN offline version metadata mismatch")
        output = args.output.resolve()
        if output.exists():
            raise ValueError("output already exists; refusing duplicate preparation")
        if not output.parent.is_dir():
            raise ValueError("output parent does not exist")
        for source in (ROOT, kernel, ksun):
            if output.is_relative_to(source) or source.is_relative_to(output):
                raise ValueError("output must be separate from all source trees")

        # Prepare exact bytes before creating the isolated worktrees. Replay
        # preflights the entire ordered series there before applying any hunk.
        makefile = (kernel / "drivers/Makefile").read_text()
        kconfig = (kernel / "drivers/Kconfig").read_text()
        if "kernelsu" in makefile or "kernelsu" in kconfig:
            raise ValueError("kernel already contains KernelSU integration")
        if kconfig.count("\nendmenu\n") != 1:
            raise ValueError("unexpected drivers/Kconfig insertion context")
        glue = text_patch("drivers/Makefile", makefile,
                          makefile + "obj-$(CONFIG_KSU) += kernelsu/\n")
        glue += text_patch("drivers/Kconfig", kconfig, kconfig.replace(
            "\nendmenu\n", '\nsource "drivers/kernelsu/Kconfig"\n\nendmenu\n'))
        # Fixed relative link makes the bundle relocatable as a unit.
        glue += (b"diff --git a/drivers/kernelsu b/drivers/kernelsu\n"
                 b"new file mode 120000\n--- /dev/null\n+++ b/drivers/kernelsu\n"
                 b"@@ -0,0 +1 @@\n+../../ksun/kernel\n\\ No newline at end of file\n")
        companions = b"".join(added_file_patch(e["destination"], inputs[e["path"]])
                              for e in lock["inputs"] if e["destination"])

        # Replace upstream version discovery (including implicit fetch) with the
        # independently verified commit count and tag for this candidate only.
        kbuild = reviewed["kernel/Kbuild"].decode()
        start = kbuild.index("# Check if this is a git repository\n")
        end = kbuild.index("KSU_NEW_DCACHE_FLUSH :=", start)
        pinned_metadata = ("# Offline metadata for the exact reviewed KSUN commit.\n"
                           f"KSU_VERSION := {metadata['ksu_version']}\n"
                           f"KSU_VERSION_TAG := {metadata['tag']}\n"
                           "ccflags-y += -DKSU_VERSION=$(KSU_VERSION)\n"
                           'ccflags-y += -DKSU_VERSION_TAG=\\"$(KSU_VERSION_TAG)\\"\n\n')
        offline_patch = text_patch("kernel/Kbuild", kbuild,
                                   kbuild[:start] + pinned_metadata + kbuild[end:])

        output.mkdir()
        created = True
        patches = output / "patches"
        patches.mkdir()
        original = ROOT / lock["inputs"][0]["path"]
        preparation_log = offline_run(sys.executable, str(ROOT / "scripts/prepare_susfs_kernel_patch.py"),
                              str(original), str(patches / lock["replay_order"][1]))
        (output / "patch-preparation.log").write_bytes(preparation_log)
        prepared = (patches / lock["replay_order"][1]).read_bytes()
        if digest(prepared) != adaptation["output_sha256"]:
            raise ValueError("prepared SUSFS patch mismatch")
        series = [record_patch(patches, lock["replay_order"][0], glue,
                               "Reviewed pinned KSUN setup mechanism; local explicit driver glue"),
                  {"path": lock["replay_order"][1], "sha256": digest(prepared),
                   "source": {"original_sha256": adaptation["input_sha256"],
                              "delta_sha256": adaptation["delta_sha256"]}},
                  record_patch(patches, lock["replay_order"][2], companions,
                               "Exact v2 companion bytes; source provenance in v2 lock")]
        ksun_series = [record_patch(patches, lock["ksun_adjustments"][0], offline_patch,
                                    "Remove implicit networking; independently checked immutable version metadata")]
        kernel_manifest = patches / "kernel-replay.json"
        ksun_manifest = patches / "ksun-replay.json"
        for path, commit, entries in ((kernel_manifest, lock["sources"]["kernel"]["commit"], series),
                                      (ksun_manifest, lock["sources"]["ksun"]["commit"], ksun_series)):
            path.write_text(json.dumps({"kernel_commit": commit, "patches": entries}, indent=2) + "\n")
        for name, source, commit in (("kernel", kernel, lock["sources"]["kernel"]["commit"]),
                                     ("ksun", ksun, lock["sources"]["ksun"]["commit"])):
            offline_git(source, "worktree", "add", "--detach", str(output / name), commit)
        for name, manifest in (("ksun", ksun_manifest), ("kernel", kernel_manifest)):
            log = offline_run(sys.executable, str(ROOT / "scripts/ksun_susfs_replay.py"),
                      str(output / name), str(manifest), "--apply")
            (output / (name + "-replay.log")).write_bytes(log)

        link = output / "kernel/drivers/kernelsu"
        if not link.is_symlink() or link.resolve() != output / "ksun/kernel":
            raise ValueError("driver link does not resolve to isolated KSUN")
        for entry in lock["inputs"]:
            if entry["destination"] and digest((output / "kernel" / entry["destination"]).read_bytes()) != entry["sha256"]:
                raise ValueError("copied companion SHA256 mismatch")
        result = {"candidate_id": lock["candidate_id"], "status": "integrated_source_only",
                  "api_review": "exact_reviewed_source_bytes_match",
                  "historical_partial_build_reused": False,
                  "production_changed": False, "build_started": False,
                  "ready_for_compilation": False, "next_compile_gates": lock["next_compile_gates"],
                  "lock_sha256": digest(WORKTREE_LOCK.read_bytes()),
                  "ordered_kernel_patches": series, "ordered_ksun_patches": ksun_series,
                  "offline_version": metadata, "source_trees": {}}
        for name in ("kernel", "ksun"):
            tree = output / name
            offline_git(tree, "add", "--all")
            diff = offline_run("git", "-C", str(tree), "diff", "--cached", "--binary", "HEAD")
            (output / (name + "-integration.diff")).write_bytes(diff)
            result["source_trees"][name] = {
                "head": offline_git(tree, "rev-parse", "HEAD"),
                "integrated_tree": offline_git(tree, "write-tree"),
                "diff_sha256": digest(diff),
                "status": offline_git(tree, "status", "--porcelain", "--untracked-files=all")}
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("PASS: reviewed API inputs, locked ordered replay, companions and isolated driver integration")
        print("RESULT:", output / "result.json")
        print("SOURCE ONLY: compilation gates remain; production, release and flash stay disabled")
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += "\n" + (exc.stderr or b"").decode(errors="replace")
        if created:
            # Preserve the first failure and worktrees. Never auto-retry/clean.
            with (output / "failure.log").open("a") as stream:
                stream.write(detail + "\n")
        print("BLOCKED:", detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

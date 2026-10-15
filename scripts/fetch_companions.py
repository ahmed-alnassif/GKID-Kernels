#!/usr/bin/env python3
"""Fetch the official root manager APK and NoMount module that match this kernel.

Cogan Manual Update pins KernelSU, KernelSU Next, BakaSU and NoMount to release
tags and records the release asset of that same tag (file name + SHA256) in
configs/upstream.lock. For the variant being built this script:

  1. checks the release tag still points at the pinned commit the kernel was
     built from, so manager/module and kernel are the same version;
  2. downloads the asset from the official release and verifies its SHA256;
  3. saves it as OUT/<prefix>-<asset name> and reports it.

Vanilla builds get nothing. Pins without recorded assets are skipped with a
warning (run Cogan Manual Update first); a moved tag or a wrong checksum fails.

Usage: fetch_companions.py --ksu KSU|KSUN|BSU|no|vnlto --susfs true|false
                           --prefix NAME --out DIR [--github-output FILE] [--summary FILE]
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cogan_manual_update as mu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"
DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}/{name}"
MANAGERS = {"KSU": ("KernelSU", "KSU_COMMIT"), "KSUN": ("KernelSU Next", "KSUN_COMMIT"),
            "BSU": ("BakaSU", "BSU_COMMIT")}


class Failure(Exception):
    pass


def tag_commit(repo, tag, lister=mu.ls_remote):
    refs = lister(f"https://github.com/{repo}.git", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


def download(url, attempts=3):
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                return response.read()
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise OSError("unreachable")


def candidate_nomount_commit(path=FEATURE_LOCK):
    for feature in json.loads(path.read_text(encoding="utf-8")).get("features", []):
        if feature.get("name") == "nomount":
            return feature.get("commit")
    return None


def newer_release(lock, pin_key, lister):
    """Upstream release tag newer than the pinned one, or None. Never fails the build."""
    _, _, url, ref = mu.PINS[pin_key]
    _, tag, error = mu.resolve(url, ref, lister)
    if error or not tag or tag == lock.get(mu.TAG_KEYS[pin_key]):
        return None
    return tag


def reminder(lock, kind, pin_key, lister):
    """Bilingual reminder to run Cogan Manual Update when upstream has a newer release."""
    tag = newer_release(lock, pin_key, lister)
    if not tag:
        return None
    label = {key: name for name, key in MANAGERS.values()}.get(pin_key, "NoMount")
    group = "nomount" if kind == "nomount" else "root-managers"
    pinned = lock.get(mu.TAG_KEYS[pin_key], "-")
    return (f"🔔 {label} {tag} tersedia / available (terpasang / pinned: {pinned}). "
            f"Jalankan / run **Cogan Manual Update** → `update` → `{group}`, lalu build ulang / then rebuild: "
            f"kernel, root manager & NoMount naik bersama / move up together.")


def fetch_one(lock, kind, pin_key, prefix, out, candidate, lister, fetch):
    """Returns (path or None, summary line)."""
    companion, tag_key = mu.COMPANIONS[pin_key], mu.TAG_KEYS[pin_key]
    label = {key: name for name, key in MANAGERS.values()}.get(pin_key, "NoMount")
    tag, name, digest = lock.get(tag_key), lock.get(companion.name_key), lock.get(companion.sha_key)
    if not (tag and name and digest):
        group = "nomount" if kind == "nomount" else "root-managers"
        return None, (f"⚠️ {label}: no release asset pinned yet; run **Cogan Manual Update** "
                      f"(`update`, `{group}`) to add it")
    note = "same tag as the kernel source"
    if candidate and kind == "manager":
        note = ("official manager; this test kernel uses the pershoot fork "
                "(accepts the official signature, build number may differ)")
    elif candidate and kind == "nomount":
        carried = candidate_nomount_commit() or "unknown"
        if carried != lock[pin_key]:
            return None, (f"⚠️ NoMount: test kernel carries NoMount {carried[:12]}, "
                          f"not {tag}; module not attached")
        note = "same commit as the NoMount in this test kernel"
    if not (candidate and kind == "manager"):
        actual = tag_commit(companion.repo, tag, lister)
        if actual != lock[pin_key]:
            raise Failure(f"{label} tag {tag} now points at {actual}, but the kernel was built from "
                          f"{lock[pin_key]}; run Cogan Manual Update before shipping a manager")
    data = fetch(DOWNLOAD.format(repo=companion.repo, tag=tag, name=name))
    actual_digest = hashlib.sha256(data).hexdigest()
    if actual_digest != digest:
        raise Failure(f"{name}: SHA256 {actual_digest} does not match the pinned {digest}")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prefix}-{name}"
    path.write_bytes(data)
    return path, f"✅ {label} {tag}: `{path.name}` ({note}); SHA256 `{digest}`"


def main(argv=None, lister=mu.ls_remote, fetch=download):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ksu", required=True)
    parser.add_argument("--susfs", default="false")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--github-output")
    parser.add_argument("--summary")
    args = parser.parse_args(argv)
    if not mu.ASSET_NAME.fullmatch(args.prefix + ".zip"):
        parser.error("unsupported --prefix")
    lock = mu.read_lock(mu.LOCK.read_text(encoding="utf-8"))
    candidate = args.ksu == "KSUN" and args.susfs == "true"
    outputs, lines, reminders, status = {}, [], [], 0
    if args.ksu in MANAGERS:
        for kind, pin_key in (("manager", MANAGERS[args.ksu][1]), ("nomount", "NOMOUNT_COMMIT")):
            try:
                path, line = fetch_one(lock, kind, pin_key, args.prefix, args.out, candidate, lister, fetch)
            except (Failure, OSError, ValueError) as exc:
                path, line, status = None, f"❌ {exc}", 1
            if path:
                outputs[kind] = str(path)
            lines.append(line)
            # The test kernel is a frozen fork: a newer official manager does not move it.
            if not (candidate and kind == "manager"):
                note = reminder(lock, kind, pin_key, lister)
                if note:
                    reminders.append(note)
    else:
        lines.append("Vanilla build: no root manager or NoMount module to attach.")
    report = ["### 📱 Root manager & NoMount", "",
              "🇮🇩 Pasang APK manager dan modul NoMount ini bersama ZIP kernel di atas: versinya sama dengan kernel.",
              "🇬🇧 Install this manager APK and NoMount module with the kernel ZIP above: they match the kernel.",
              "",
              "🔗 🇮🇩 Versi kernel, root manager dan NoMount dikunci bersama oleh **Cogan Manual Update** "
              "(`configs/upstream.lock`); build ini hanya memakai pin tersebut.",
              "🔗 🇬🇧 **Cogan Manual Update** pins the kernel, root manager and NoMount versions together "
              "(`configs/upstream.lock`); this build only uses those pins.",
              "", *[f"- {line}" for line in lines], ""]
    if reminders:
        report += ["#### 🔔 Pengingat / Reminder", "", *[f"- {note}" for note in reminders], ""]
    print("\n".join(report))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(report) + "\n")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.writelines(f"{key}={value}\n" for key, value in outputs.items())
    return status


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prepare the direct downloads of a kernel build, with names that say what they are.

  1-KERNEL_Cogan-<linux>_<variant>_<release>.zip   flash with Kernel Flasher
  2-MANAGER_<root manager>_<tag>.apk                official root manager APK
  3-MANAGER-SPOOFED_<root manager>_<tag>.apk        official spoofed build (if published)
  4-NOMOUNT-MODULE_<tag>.zip                        official NoMount module

Cogan Manual Update pins KernelSU, KernelSU Next, BakaSU and NoMount to release
tags and records the release assets of that same tag (name + SHA256) in
configs/upstream.lock. For each pinned asset this script checks the tag still
points at the commit the kernel was built from, downloads the asset from the
official release, verifies its SHA256 and saves it under the name above. It
writes one table to the run summary and a reminder when upstream has a newer
release than the pin. Vanilla builds get only the kernel. A moved tag or a wrong
checksum fails (after the kernel is prepared, so it can still be downloaded).

Usage: prepare_downloads.py --ksu KSU|KSUN|BSU|no|vnlto --susfs true|false
           --variant V --release R --linux-version 6.1.N --artifacts DIR --out DIR
           [--suffix _<matrix name>] [--github-output FILE] [--summary FILE]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cogan_manual_update as mu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"
DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}/{name}"
# matrix KSU value -> (label for people and file names, pin key)
MANAGERS = {"KSU": ("KernelSU", "KSU_COMMIT"), "KSUN": ("KernelSU-Next", "KSUN_COMMIT"),
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


def checked_name(name):
    if not mu.ASSET_NAME.fullmatch(name):
        raise Failure(f"unsupported download name {name!r}")
    return name


def kernel_download(artifacts, out, linux_version, variant, release, suffix):
    zips = sorted(Path(artifacts).glob("*.zip"))
    if len(zips) != 1:
        return None, f"⚠️ Kernel: expected one ZIP in {artifacts}, found {len(zips)}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / checked_name(f"1-KERNEL_Cogan-{linux_version}_{variant}_{release}{suffix}.zip")
    shutil.copyfile(zips[0], path)
    return path, None


def fetch_asset(lock, pin_key, companion, filename, out, verify_tag, lister, fetch):
    """Download one pinned release asset under filename, or raise Failure."""
    tag = lock[mu.TAG_KEYS[pin_key]]
    name, digest = lock[companion.name_key], lock[companion.sha_key]
    if verify_tag:
        actual = tag_commit(companion.repo, tag, lister)
        if actual != lock[pin_key]:
            raise Failure(f"{companion.repo} tag {tag} now points at {actual}, but the kernel was built "
                          f"from {lock[pin_key]}; run Cogan Manual Update before shipping it")
    # A CI-only upstream build is downloaded from this repository's mirror prerelease.
    source = (DOWNLOAD.format(repo=os.environ.get("GITHUB_REPOSITORY", "cogan17/Cogan"), tag=mu.MIRROR_TAG,
                              name=name) if companion.ci
              else DOWNLOAD.format(repo=companion.repo, tag=tag, name=name))
    data = fetch(source)
    actual_digest = hashlib.sha256(data).hexdigest()
    if actual_digest != digest:
        raise Failure(f"{name}: SHA256 {actual_digest} does not match the pinned {digest}")
    out.mkdir(parents=True, exist_ok=True)
    path = out / checked_name(filename)
    path.write_bytes(data)
    return path


def newer_release(lock, pin_key, lister):
    """Upstream release tag newer than the pinned one, or None. Never fails the build."""
    _, _, url, ref = mu.PINS[pin_key]
    _, tag, error = mu.resolve(url, ref, lister)
    if error or not tag or tag == lock.get(mu.TAG_KEYS[pin_key]):
        return None
    return tag


def reminder(lock, label, group, pin_key, lister):
    tag = newer_release(lock, pin_key, lister)
    if not tag:
        return None
    pinned = lock.get(mu.TAG_KEYS[pin_key], "-")
    return (f"🔔 {label} {tag} tersedia / available (terpasang / pinned: {pinned}). "
            f"Jalankan / run **Cogan Manual Update** → `update` → `{group}`, lalu build ulang / then rebuild: "
            f"kernel, root manager & NoMount naik bersama / move up together.")


def prepare(args, lock, lister, fetch):
    """Returns (outputs, table rows, notes, reminders, status)."""
    outputs, rows, notes, reminders, status = {}, [], [], [], 0
    path, problem = kernel_download(args.artifacts, args.out, args.linux_version, args.variant,
                                    args.release, args.suffix)
    if path:
        outputs["kernel"] = str(path)
        rows.append(("1", path.name, f"Kernel Cogan {args.linux_version} ({args.variant})",
                     "Flash di / with **Kernel Flasher**"))
    else:
        notes.append(problem)
    if args.ksu not in MANAGERS:
        notes.append("Vanilla: tanpa root manager & NoMount / no root manager or NoMount.")
        return outputs, rows, notes, reminders, status
    candidate = args.ksu == "KSUN" and args.susfs == "true"
    label, pin_key = MANAGERS[args.ksu]
    tag = lock.get(mu.TAG_KEYS[pin_key])
    manager, *spoofed = mu.COMPANIONS[pin_key]
    plan = [("manager", "2", manager, "2-MANAGER"), *[("spoofed", "3", s, "3-MANAGER-SPOOFED") for s in spoofed],
            ("nomount", "4", mu.COMPANIONS["NOMOUNT_COMMIT"][0], "4-NOMOUNT-MODULE")]
    for kind, number, companion, prefix in plan:
        key = "NOMOUNT_COMMIT" if kind == "nomount" else pin_key
        item_tag = lock.get(mu.TAG_KEYS[key])
        if not (item_tag and lock.get(companion.name_key) and lock.get(companion.sha_key)):
            if kind == "spoofed" and item_tag:
                notes.append(f"ℹ️ {label} {item_tag}: belum ada manager spoofed resmi yang dipin / "
                             f"no official spoofed manager pinned.")
            elif kind != "spoofed":
                group = "nomount" if kind == "nomount" else "root-managers"
                notes.append(f"⚠️ {'NoMount' if kind == 'nomount' else label}: belum dipin / not pinned yet; "
                             f"jalankan / run **Cogan Manual Update** → `update` → `{group}`")
            continue
        if candidate and kind == "nomount" and candidate_nomount_commit() != lock[key]:
            notes.append(f"⚠️ NoMount: kernel uji memakai NoMount lain / the test kernel carries a different "
                         f"NoMount; module not attached")
            continue
        filename = (f"{prefix}_{item_tag}{args.suffix}.zip" if kind == "nomount"
                    else f"{prefix}_{label}_{item_tag}{args.suffix}.apk")
        try:
            # The KSUN test kernel is the pershoot fork: no tag to compare for its manager.
            path = fetch_asset(lock, key, companion, filename, args.out,
                               not (candidate and kind != "nomount"), lister, fetch)
        except (Failure, OSError, ValueError) as exc:
            notes.append(f"❌ {exc}")
            status = 1
            continue
        outputs[kind] = str(path)
        if kind == "manager":
            what = f"Root manager {label} {item_tag}"
            how = "Install APK (pilih 2 **atau** 3 / pick 2 **or** 3)" if spoofed else "Install APK"
        elif kind == "spoofed":
            what = f"{label} {item_tag} spoofed: nama paket acak, lebih sulit dideteksi / random package name"
            how = "Install APK (pilih 2 **atau** 3 / pick 2 **or** 3)"
        else:
            what = f"Modul / module NoMount {item_tag}"
            how = "Pasang di manager → Modul / install in manager → Modules"
        rows.append((number, path.name, what, how))
        notes.append(f"✅ `{path.name}` ← `{lock[companion.name_key]}` SHA256 `{lock[companion.sha_key]}`")
    if candidate:
        notes.append("ℹ️ Kernel uji / test kernel = fork pershoot: menerima manager KSUN resmi, "
                     "nomor build bisa beda / accepts the official KSUN manager, build number may differ.")
    for kind, key, group in (("manager", pin_key, "root-managers"), ("nomount", "NOMOUNT_COMMIT", "nomount")):
        if candidate and kind == "manager":
            continue  # a newer official manager does not move the frozen test kernel
        note = reminder(lock, label if kind == "manager" else "NoMount", group, key, lister)
        if note:
            reminders.append(note)
    return outputs, rows, notes, reminders, status


def report(rows, notes, reminders):
    lines = ["### 📦 Unduhan / Downloads", "",
             "| # | File | Isi / What | Cara pakai / How to use |", "|---|---|---|---|",
             *[f"| {n} | `{name}` | {what} | {how} |" for n, name, what, how in rows], "",
             "Abaikan / ignore `build-…` & `build-env-…`: file internal / internal files.", "",
             "🔗 Versi kernel, root manager & NoMount dikunci bersama oleh **Cogan Manual Update** "
             "(`configs/upstream.lock`) / **Cogan Manual Update** pins these versions together.", ""]
    if notes:
        lines += ["<details><summary>Detail & SHA256</summary>", "", *[f"- {note}" for note in notes], "",
                  "</details>", ""]
    if reminders:
        lines += ["#### 🔔 Pengingat / Reminder", "", *[f"- {note}" for note in reminders], ""]
    return "\n".join(lines) + "\n"


def main(argv=None, lister=mu.ls_remote, fetch=download):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ksu", required=True)
    parser.add_argument("--susfs", default="false")
    parser.add_argument("--variant", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--linux-version", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suffix", default="")
    parser.add_argument("--github-output")
    parser.add_argument("--summary")
    args = parser.parse_args(argv)
    lock = mu.read_lock(mu.LOCK.read_text(encoding="utf-8"))
    try:
        outputs, rows, notes, reminders, status = prepare(args, lock, lister, fetch)
    except Failure as exc:  # unusable names: nothing can be published safely
        outputs, rows, notes, reminders, status = {}, [], [f"❌ {exc}"], [], 1
    text = report(rows, notes, reminders)
    print(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.writelines(f"{key}={value}\n" for key, value in outputs.items())
    return status


if __name__ == "__main__":
    sys.exit(main())

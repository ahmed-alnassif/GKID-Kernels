#!/usr/bin/env python3
"""Cogan Manual Update: report upstream revisions and, on request, bump pins.

Scope: kernel 6.1 (GKID) only, by owner decision.

The only writer of configs/upstream.lock. Owner-triggered via the
"Cogan Manual Update" workflow; the kernel build workflow only reads the lock.

  check  : compare every pin with upstream and write a report (no changes)
  update : rewrite the selected pins to the latest upstream revision

Usage:
  python3 scripts/cogan_manual_update.py --mode check|update \
      [--components all|root-managers|susfs|nomount|anykernel|kernel-6.1] \
      [--summary FILE] [--changes FILE]
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/upstream.lock"
SHA = re.compile(r"[0-9a-f]{40}")
STABLE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
LINE = re.compile(r"([A-Z][A-Z0-9_]*)=(v\d+\.\d+\.\d+|[0-9a-f]{40})")

SUSFS = "https://gitlab.com/simonpunk/susfs4ksu.git"
# key -> (group, label, repository, ref). A ref of "latest-stable-tag" means
# the highest vX.Y.Z tag (pre-release, -legacy and other suffixes excluded).
PINS = {
    "KSU_COMMIT": ("root-managers", "KernelSU", "https://github.com/tiann/KernelSU.git", "refs/heads/main"),
    "BSU_COMMIT": ("root-managers", "BakaSU", "https://github.com/Baka-SU/BakaSU.git", "refs/heads/main"),
    "KSUN_COMMIT": ("root-managers", "KernelSU Next", "https://github.com/KernelSU-Next/KernelSU-Next.git", "latest-stable-tag"),
    "NOMOUNT_SETUP_COMMIT": ("nomount", "NoMount setup.sh", "https://github.com/maxsteeel/nomount.git", "refs/heads/dev"),
    "NOMOUNT_COMMIT": ("nomount", "NoMount source", "https://github.com/maxsteeel/nomount.git", "refs/heads/master"),
    "ANYKERNEL_COMMIT": ("anykernel", "AnyKernel3", "https://github.com/ahmed-alnassif/AK3-GKID.git", "HEAD"),
    "KERNEL_COMMIT_6_1": ("kernel-6.1", "Kernel GKID 6.1", "https://github.com/ahmed-alnassif/GKI-Duchamp-6.1.git", "refs/heads/GKID-6.1"),
    "SUSFS_COMMIT_6_1": ("susfs", "SUSFS 6.1", SUSFS, "refs/heads/gki-android14-6.1"),
}
GROUPS = sorted({group for group, *_ in PINS.values()})
LOCAL_FINGERPRINTS = [
    ("Networking / BBRv3", ["kernel-patches/bbrv3/bbrv3.patch", "configs/custom.config"]),
    ("Clean LTO", ["configs/gki_defconfig.sh", "build.sh"]),
]


def read_lock(text):
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        match = LINE.fullmatch(raw)
        if not match:
            raise ValueError(f"Malformed lock line {number}: {raw}")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"Duplicate lock key: {key}")
        values[key] = value
    missing = [key for key in [*PINS, "KSUN_REF"] if key not in values]
    if missing:
        raise ValueError("Lock is missing " + ", ".join(missing))
    return values


def write_lock(text, updates):
    """Replace values of existing keys only, preserving comments and order."""
    out, seen = [], set()
    for raw in text.splitlines():
        match = LINE.fullmatch(raw)
        if match and match.group(1) in updates:
            key = match.group(1)
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(raw)
    unknown = set(updates) - seen
    if unknown:
        raise ValueError("Cannot update keys absent from lock: " + ", ".join(sorted(unknown)))
    result = "\n".join(out) + "\n"
    read_lock(result)
    return result


def ls_remote(url, *patterns, options=(), timeout=40):
    # Options must precede the repository; later arguments are ref patterns.
    result = subprocess.run(["git", "ls-remote", *options, url, *patterns],
                            capture_output=True, text=True, timeout=timeout, check=True)
    refs = {}
    for line in result.stdout.splitlines():
        sha, name = line.split("\t", 1)
        refs[name] = sha.lower()
    return refs


def latest_stable_tag(refs):
    """Return (tag, commit) for the highest vX.Y.Z tag, peeling annotated tags."""
    best = None
    for name in refs:
        if not name.startswith("refs/tags/") or name.endswith("^{}"):
            continue
        tag = name[len("refs/tags/"):]
        match = STABLE_TAG.fullmatch(tag)
        if match:
            version = tuple(int(part) for part in match.groups())
            if best is None or version > best[0]:
                best = (version, tag)
    if best is None:
        return None, None
    tag = best[1]
    commit = refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")
    return tag, commit


def resolve(url, ref, lister=ls_remote):
    """Return (commit, tag or None, error or None) for one upstream source."""
    try:
        if ref == "latest-stable-tag":
            tag, commit = latest_stable_tag(lister(url, options=("--tags",)))
            if not commit or not SHA.fullmatch(commit):
                return None, None, "No stable vX.Y.Z tag"
            return commit, tag, None
        commit = lister(url, ref).get(ref)
        if not commit or not SHA.fullmatch(commit):
            return None, None, "Ref not found"
        return commit, None, None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, None, type(exc).__name__


def select(components):
    wanted = {part.strip() for part in components.split(",") if part.strip()}
    if not wanted or "all" in wanted:
        return set(GROUPS)
    unknown = wanted - set(GROUPS)
    if unknown:
        raise ValueError("Unknown components: " + ", ".join(sorted(unknown)))
    return wanted


def plan(lock, groups, lister=ls_remote):
    """Compare pins with upstream. Returns (rows, updates) without side effects."""
    rows, updates = [], {}
    for key, (group, label, url, ref) in PINS.items():
        current = lock[key]
        commit, tag, error = resolve(url, ref, lister)
        shown_ref = tag or ref.replace("refs/heads/", "")
        if key == "KSUN_COMMIT":
            current_label = f"{lock['KSUN_REF']} {current[:12]}"
        else:
            current_label = current[:12]
        if error:
            status = "UNAVAILABLE: " + error
        elif commit == current and (tag is None or tag == lock.get("KSUN_REF")):
            status = "UP TO DATE"
        else:
            status = "UPDATE AVAILABLE"
            if group in groups:
                updates[key] = commit
                if tag:
                    updates["KSUN_REF"] = tag
        latest = f"{tag} {commit[:12]}" if tag and commit else (commit or "-")[:12]
        rows.append((label, group, shown_ref, current_label, latest, status))
    return rows, updates


def report(rows, fingerprints, mode, groups, updates):
    lines = [
        f"## Cogan Manual Update — mode `{mode}`",
        "",
        "Owner-triggered only. The kernel build workflow only compiles the pinned "
        "commits in `configs/upstream.lock`; it never updates them.",
        "",
        "Selected components: " + ", ".join(sorted(groups)),
        "",
        "| Component | Group | Upstream ref | Pinned | Latest upstream | Status |",
        "|---|---|---|---|---|---|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    lines += ["", "### Cogan local fingerprints", "", "| Component | SHA256 (12) |", "|---|---|"]
    lines += ["| " + " | ".join(row) + " |" for row in fingerprints]
    lines.append("")
    if mode == "update":
        if updates:
            lines.append("**Proposed pin changes** (pull request to `dev`; review, merge, then run a build):")
            lines += [f"- `{key}` → `{value}`" for key, value in sorted(updates.items())]
        else:
            lines.append("**No pin changes**: the selected components are already up to date.")
    lines += ["", "A newer upstream revision is not proof of compatibility. "
              "Build and test after merging the update."]
    return "\n".join(lines) + "\n"


def collect_fingerprints(root=ROOT):
    rows = []
    for label, paths in LOCAL_FINGERPRINTS:
        missing = [path for path in paths if not (root / path).is_file()]
        if missing:
            rows.append((label, "MISSING: " + ", ".join(missing)))
            continue
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.encode())
            digest.update((root / path).read_bytes())
        rows.append((label, digest.hexdigest()[:12]))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["check", "update"], required=True)
    parser.add_argument("--components", default="all")
    parser.add_argument("--summary", help="Append the Markdown report to this file")
    parser.add_argument("--changes", help="Write updated KEY=VALUE lines here (update mode)")
    args = parser.parse_args(argv)

    text = LOCK.read_text(encoding="utf-8")
    lock = read_lock(text)
    groups = select(args.components)
    rows, updates = plan(lock, groups)
    output = report(rows, collect_fingerprints(), args.mode, groups, updates)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(output)
    print(output)

    if args.mode == "update" and updates:
        LOCK.write_text(write_lock(text, updates), encoding="utf-8")
    if args.changes:
        Path(args.changes).write_text(
            "".join(f"{key}={value}\n" for key, value in sorted(updates.items()))
            if args.mode == "update" else "", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

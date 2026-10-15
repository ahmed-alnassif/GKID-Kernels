#!/usr/bin/env python3
"""Cogan Manual Update: report upstream revisions and, on request, bump pins.

Scope: kernel 6.1 (GKID) only, by owner decision.

The only writer of configs/upstream.lock. Owner-triggered via the
"Cogan Manual Update" workflow; the kernel build workflow only reads the lock.

  check  : compare every pin with upstream and write a report (no changes)
  update : rewrite the selected pins to the latest upstream revision

Usage:
  python3 scripts/cogan_manual_update.py --mode check|update \
      [--components all|root-managers|susfs|nomount|bbg|anykernel|kernel-6.1|toolchain] \
      [--summary FILE] [--changes FILE]
"""
import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/upstream.lock"
SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
STABLE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
RELEASE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?")
ASSET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\.(?:apk|zip)")
LINE = re.compile(r"([A-Z][A-Z0-9_]*)=(v\d+\.\d+\.\d+(?:-rc\d+)?|[0-9a-f]{40}|[0-9a-f]{64}|\d{8}|"
                  r"[A-Za-z0-9][A-Za-z0-9._+-]*\.(?:apk|zip))")
RELEASE_API = "https://api.github.com/repos/{repo}/releases/tags/{tag}"
SUBLEVEL_KEY = re.compile(r"KERNEL_COMMIT_6_1_(\d+)")
KERNEL_RAW = "https://raw.githubusercontent.com/ahmed-alnassif/GKI-Duchamp-6.1/{commit}/Makefile"
NEUTRON_REPO = "https://github.com/Neutron-Toolchains/clang-build-catalogue.git"
NEUTRON_ASSET = ("https://github.com/Neutron-Toolchains/clang-build-catalogue/releases/download/"
                 "{tag}/neutron-clang-{tag}.tar.zst")
NEUTRON_TAG = re.compile(r"(\d{2})(\d{2})(\d{4})")  # DDMMYYYY

SUSFS = "https://gitlab.com/simonpunk/susfs4ksu.git"
# key -> (group, label, repository, ref). A ref of "latest-stable-tag" means
# the highest vX.Y.Z tag (pre-release, -legacy and other suffixes excluded);
# "latest-release-tag" also accepts vX.Y.Z-rcN release candidates.
# Root managers and NoMount follow release tags so the kernel is built from
# exactly the source of the official manager APK / module ZIP (owner decision
# 2026-10-16): the kernel only accepts the developer-signed manager.
PINS = {
    "KSU_COMMIT": ("root-managers", "KernelSU", "https://github.com/tiann/KernelSU.git", "latest-stable-tag"),
    "BSU_COMMIT": ("root-managers", "BakaSU", "https://github.com/Baka-SU/BakaSU.git", "latest-release-tag"),
    "KSUN_COMMIT": ("root-managers", "KernelSU Next", "https://github.com/KernelSU-Next/KernelSU-Next.git", "latest-stable-tag"),
    "NOMOUNT_SETUP_COMMIT": ("nomount", "NoMount setup.sh", "https://github.com/maxsteeel/nomount.git", "refs/heads/dev"),
    "NOMOUNT_COMMIT": ("nomount", "NoMount source", "https://github.com/maxsteeel/nomount.git", "latest-stable-tag"),
    "BBG_COMMIT": ("bbg", "Baseband Guard (BBG)", "https://github.com/vc-teahouse/Baseband-guard.git", "refs/heads/main"),
    "ANYKERNEL_COMMIT": ("anykernel", "AnyKernel3", "https://github.com/ahmed-alnassif/AK3-GKID.git", "HEAD"),
    "KERNEL_COMMIT_6_1": ("kernel-6.1", "Kernel GKID 6.1", "https://github.com/ahmed-alnassif/GKI-Duchamp-6.1.git", "refs/heads/GKID-6.1"),
    "SUSFS_COMMIT_6_1": ("susfs", "SUSFS 6.1", SUSFS, "refs/heads/gki-android14-6.1"),
}
GROUPS = sorted({group for group, *_ in PINS.values()} | {"toolchain"})
REQUIRED = [*PINS, "KSUN_REF", "NEUTRON_RELEASE", "NEUTRON_SHA256"]
# Tag-pinned sources: commit key -> lock key holding the tag.
TAG_KEYS = {"KSU_COMMIT": "KSU_REF", "BSU_COMMIT": "BSU_REF",
            "KSUN_COMMIT": "KSUN_REF", "NOMOUNT_COMMIT": "NOMOUNT_REF"}
# Release asset shipped next to the kernel, from the same tag as the pinned source.
# required: without the asset the pin is not moved (a manager must match the kernel).
Companion = collections.namedtuple("Companion", "repo name_key sha_key suffix required")
COMPANIONS = {
    "KSU_COMMIT": Companion("tiann/KernelSU", "KSU_MANAGER_APK", "KSU_MANAGER_SHA256", ".apk", True),
    "BSU_COMMIT": Companion("Baka-SU/BakaSU", "BSU_MANAGER_APK", "BSU_MANAGER_SHA256", ".apk", True),
    "KSUN_COMMIT": Companion("KernelSU-Next/KernelSU-Next", "KSUN_MANAGER_APK", "KSUN_MANAGER_SHA256", ".apk", True),
    "NOMOUNT_COMMIT": Companion("maxsteeel/nomount", "NOMOUNT_MODULE_ZIP", "NOMOUNT_MODULE_SHA256", ".zip", False),
}
ASSET_EXCLUDE = ("spoof", "debug")
# Optional lock keys (added by an update) -> the pin line they are written after.
ANCHORS = {}
for _pin, _tag_key in TAG_KEYS.items():
    if _tag_key not in REQUIRED:
        ANCHORS[_tag_key] = _pin
for _pin, _companion in COMPANIONS.items():
    ANCHORS[_companion.name_key] = _pin
    ANCHORS[_companion.sha_key] = _pin
OPTIONAL = list(ANCHORS)
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
        if not value_fits(key, value):
            raise ValueError(f"Bad value for {key} on lock line {number}: {value}")
        values[key] = value
    missing = [key for key in REQUIRED if key not in values]
    if missing:
        raise ValueError("Lock is missing " + ", ".join(missing))
    unknown = [key for key in values
               if key not in REQUIRED and key not in ANCHORS and not SUBLEVEL_KEY.fullmatch(key)]
    if unknown:
        raise ValueError("Unknown lock keys: " + ", ".join(unknown))
    return values


def value_fits(key, value):
    """Each key family has exactly one value shape."""
    if "_COMMIT" in key:  # KSU_COMMIT, SUSFS_COMMIT_6_1, KERNEL_COMMIT_6_1_177, ...
        return bool(SHA.fullmatch(value))
    if key.endswith("_SHA256"):
        return bool(SHA256.fullmatch(value))
    if key.endswith("_REF"):
        return bool(RELEASE_TAG.fullmatch(value))
    if key.endswith("_APK"):
        return bool(ASSET_NAME.fullmatch(value)) and value.endswith(".apk")
    if key.endswith("_ZIP"):
        return bool(ASSET_NAME.fullmatch(value)) and value.endswith(".zip")
    if key == "NEUTRON_RELEASE":
        return bool(re.fullmatch(r"\d{8}", value))
    return True


def write_lock(text, updates):
    """Replace existing values, preserving comments and order.

    A new KERNEL_COMMIT_6_1_<sublevel> key is inserted after the last sublevel
    line, and a new optional key (release tag, companion asset) after its pin
    line; any other key absent from the lock is an error.
    """
    out, seen, last_sublevel = [], set(), None
    for raw in text.splitlines():
        match = LINE.fullmatch(raw)
        if match and match.group(1) in updates:
            key = match.group(1)
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(raw)
        if match and SUBLEVEL_KEY.fullmatch(match.group(1)):
            last_sublevel = len(out)
    added = sorted(set(updates) - seen, key=lambda key: (len(key), key))
    unknown = [key for key in added if not SUBLEVEL_KEY.fullmatch(key) and key not in ANCHORS]
    if unknown:
        raise ValueError("Cannot update keys absent from lock: " + ", ".join(unknown))
    sublevels = [key for key in added if SUBLEVEL_KEY.fullmatch(key)]
    if sublevels:
        if last_sublevel is None:
            raise ValueError("Lock has no KERNEL_COMMIT_6_1_<sublevel> entries")
        out[last_sublevel:last_sublevel] = [f"{key}={updates[key]}" for key in sublevels]
    for key in [key for key in OPTIONAL if key in added]:
        anchor = ANCHORS[key]
        position = next((index for index, line in enumerate(out) if line.startswith(anchor + "=")), None)
        if position is None:
            raise ValueError(f"Lock has no {anchor} line for {key}")
        position += 1
        while position < len(out) and ANCHORS.get(out[position].split("=", 1)[0]) == anchor:
            position += 1
        out.insert(position, f"{key}={updates[key]}")
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


def latest_tag(refs, allow_rc=False):
    """Return (tag, commit) for the highest vX.Y.Z (or vX.Y.Z-rcN) tag, peeling annotated tags.

    A final release ranks above its own release candidates.
    """
    best = None
    pattern = RELEASE_TAG if allow_rc else STABLE_TAG
    for name in refs:
        if not name.startswith("refs/tags/") or name.endswith("^{}"):
            continue
        tag = name[len("refs/tags/"):]
        match = pattern.fullmatch(tag)
        if match:
            major, minor, patch, *rc = match.groups()
            rc = rc[0] if rc else None
            version = (int(major), int(minor), int(patch), rc is None, int(rc or 0))
            if best is None or version > best[0]:
                best = (version, tag)
    if best is None:
        return None, None
    tag = best[1]
    commit = refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")
    return tag, commit


def latest_stable_tag(refs):
    """Return (tag, commit) for the highest vX.Y.Z tag, peeling annotated tags."""
    return latest_tag(refs)


def resolve(url, ref, lister=ls_remote):
    """Return (commit, tag or None, error or None) for one upstream source."""
    try:
        if ref in ("latest-stable-tag", "latest-release-tag"):
            tag, commit = latest_tag(lister(url, options=("--tags",)),
                                     allow_rc=ref == "latest-release-tag")
            if not commit or not SHA.fullmatch(commit):
                return None, None, "No release vX.Y.Z tag"
            return commit, tag, None
        commit = lister(url, ref).get(ref)
        if not commit or not SHA.fullmatch(commit):
            return None, None, "Ref not found"
        return commit, None, None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, None, type(exc).__name__


def fetch_url(url, timeout=40):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def release_assets(repo, tag, opener=urllib.request.urlopen):
    """Assets of the GitHub release for tag: [{name, url, digest}]. Empty if no release."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(RELEASE_API.format(repo=repo, tag=tag), headers=headers)
    try:
        with opener(request, timeout=40) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return [{"name": asset.get("name", ""), "url": asset.get("browser_download_url", ""),
             "digest": asset.get("digest") or ""} for asset in data.get("assets", [])]


def pick_asset(assets, suffix):
    """The single official asset ending in suffix (spoofed/debug builds excluded)."""
    candidates = [asset for asset in assets if asset["name"].lower().endswith(suffix)
                  and not any(word in asset["name"].lower() for word in ASSET_EXCLUDE)]
    # Narrow step by step: release builds, then the universal APK of per-ABI splits
    # (BakaSU ships arm64-v8a, armeabi-v7a, x86_64 and universal).
    for word in ("release", "universal"):
        if len(candidates) > 1:
            preferred = [asset for asset in candidates if word in asset["name"].lower()]
            candidates = preferred or candidates
    if len(candidates) != 1:
        names = ", ".join(asset["name"] for asset in candidates) or "none"
        raise ValueError(f"expected one {suffix} asset, found {len(candidates)} ({names})")
    asset = candidates[0]
    if not ASSET_NAME.fullmatch(asset["name"]):
        raise ValueError(f"unsupported asset name {asset['name']!r}")
    return asset


def asset_sha256(asset, opener=urllib.request.urlopen):
    """SHA256 of a release asset: GitHub's recorded digest, else hash the download."""
    digest = asset.get("digest", "")
    if digest.startswith("sha256:") and SHA256.fullmatch(digest[7:]):
        return digest[7:]
    hasher = hashlib.sha256()
    with opener(asset["url"], timeout=300) as response:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def companion_for(key, tag, assets_of=release_assets, sha_of=asset_sha256):
    """(name, sha256, None) for the release asset next to a tag pin, or (None, None, reason)."""
    companion = COMPANIONS[key]
    try:
        asset = pick_asset(assets_of(companion.repo, tag), companion.suffix)
        digest = sha_of(asset)
        if not SHA256.fullmatch(digest):
            raise ValueError("bad digest")
        return asset["name"], digest, None
    except (OSError, ValueError, KeyError) as exc:
        return None, None, f"no usable {companion.suffix} in release {tag}: {exc}"


def kernel_sublevel(commit, fetch=fetch_url):
    """Return N for a GKID 6.1.N commit, read from its top-level Makefile."""
    head = fetch(KERNEL_RAW.format(commit=commit))[:2000]
    fields = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL) = (\d+)$", head, re.MULTILINE))
    if fields.get("VERSION") != "6" or fields.get("PATCHLEVEL") != "1" or "SUBLEVEL" not in fields:
        raise ValueError("Not a 6.1 kernel Makefile")
    return int(fields["SUBLEVEL"])


def latest_neutron(refs):
    """Newest DDMMYYYY release tag, compared by date."""
    best = None
    for name in refs:
        if name.startswith("refs/tags/") and not name.endswith("^{}"):
            match = NEUTRON_TAG.fullmatch(name[len("refs/tags/"):])
            if match:
                day, month, year = match.groups()
                key = (year, month, day)
                if best is None or key > best[0]:
                    best = (key, day + month + year)
    return best[1] if best else None


def archive_sha256(tag, opener=urllib.request.urlopen):
    digest = hashlib.sha256()
    with opener(NEUTRON_ASSET.format(tag=tag), timeout=300) as response:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select(components):
    wanted = {part.strip() for part in components.split(",") if part.strip()}
    if not wanted or "all" in wanted:
        return set(GROUPS)
    unknown = wanted - set(GROUPS)
    if unknown:
        raise ValueError("Unknown components: " + ", ".join(sorted(unknown)))
    return wanted


def current_sublevel(lock):
    """Sublevel whose lock entry equals the Auto pin (KERNEL_COMMIT_6_1)."""
    matches = [int(SUBLEVEL_KEY.fullmatch(key).group(1)) for key, value in lock.items()
               if SUBLEVEL_KEY.fullmatch(key) and value == lock["KERNEL_COMMIT_6_1"]]
    return max(matches) if matches else None


def plan(lock, groups, lister=ls_remote, sublevel_of=kernel_sublevel, sha256_of=archive_sha256,
         assets_of=release_assets, asset_sha_of=asset_sha256):
    """Compare pins with upstream. Returns (rows, updates) without side effects."""
    rows, updates = [], {}
    for key, (group, label, url, ref) in PINS.items():
        current = lock[key]
        commit, tag, error = resolve(url, ref, lister)
        tag_key, companion = TAG_KEYS.get(key), COMPANIONS.get(key)
        new_sublevel, asset, digest, note = None, None, None, ""
        if key == "KERNEL_COMMIT_6_1" and not error and commit != current:
            try:
                new_sublevel = sublevel_of(commit)
            except (OSError, ValueError) as exc:
                error = "Sublevel unreadable (" + type(exc).__name__ + ")"
        if companion and tag and not error and group in groups:
            asset, digest, reason = companion_for(key, tag, assets_of, asset_sha_of)
            if reason and companion.required:
                error = reason  # never pin a kernel source whose manager APK is missing
            elif reason:
                note = " (" + reason + ")"
        shown_ref = tag or ref.replace("refs/heads/", "")
        if tag_key:
            current_label = f"{lock.get(tag_key, '-')} {current[:12]}"
        elif key == "KERNEL_COMMIT_6_1" and current_sublevel(lock) is not None:
            current_label = f"6.1.{current_sublevel(lock)} {current[:12]}"
        else:
            current_label = current[:12]
        if companion and lock.get(companion.name_key):
            current_label += " · " + lock[companion.name_key]
        same = commit == current and (tag is None or tag == lock.get(tag_key))
        if asset:
            same = same and (lock.get(companion.name_key), lock.get(companion.sha_key)) == (asset, digest)
        if error:
            status = "UNAVAILABLE: " + error
        elif same:
            status = "UP TO DATE" + note
        else:
            status = "UPDATE AVAILABLE" + note
            if group in groups:
                proposal = {key: commit}
                if tag_key and tag:
                    proposal[tag_key] = tag
                if asset:
                    proposal[companion.name_key] = asset
                    proposal[companion.sha_key] = digest
                if new_sublevel is not None:
                    proposal[f"KERNEL_COMMIT_6_1_{new_sublevel}"] = commit
                updates.update({name: value for name, value in proposal.items() if lock.get(name) != value})
        latest = f"{tag} {commit[:12]}" if tag and commit else (commit or "-")[:12]
        if new_sublevel is not None:
            latest = f"6.1.{new_sublevel} {latest}"
        if asset:
            latest += " · " + asset
        rows.append((label, group, shown_ref, current_label, latest, status))
    rows.append(plan_toolchain(lock, groups, updates, lister, sha256_of))
    return rows, updates


def plan_toolchain(lock, groups, updates, lister, sha256_of):
    current = lock["NEUTRON_RELEASE"]
    try:
        latest = latest_neutron(lister(NEUTRON_REPO, options=("--tags",)))
        error = None if latest else "No DDMMYYYY release tag"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        latest, error = None, type(exc).__name__
    if not error and latest != current and "toolchain" in groups:
        try:
            digest = sha256_of(latest)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("bad digest")
            updates["NEUTRON_RELEASE"] = latest
            updates["NEUTRON_SHA256"] = digest
        except (OSError, ValueError) as exc:
            error = "Archive unreadable (" + type(exc).__name__ + ")"
    if error:
        status = "UNAVAILABLE: " + error
    else:
        status = "UP TO DATE" if latest == current else "UPDATE AVAILABLE"
    return ("Neutron clang", "toolchain", "release", current, latest or "-", status)


def report(rows, fingerprints, mode, groups, updates, lock_keys=()):
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
    added = sorted(int(SUBLEVEL_KEY.fullmatch(key).group(1)) for key in updates
                   if SUBLEVEL_KEY.fullmatch(key))
    if added:
        lines.append(f"Kernel Sublevel: 6.1.{added[-1]} becomes **lts** (latest) and can also be typed as "
                     f"`{added[-1]}` in the build form; older sublevels stay available.")
        lines.append("")
    pinned = sorted(int(SUBLEVEL_KEY.fullmatch(key).group(1)) for key in lock_keys if SUBLEVEL_KEY.fullmatch(key))
    if pinned:
        lines.append(f"Available Kernel Sublevel values: lts (= 6.1.{max(pinned)}), {pinned[0]}–{pinned[-1]}.")
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
    output = report(rows, collect_fingerprints(), args.mode, groups, updates,
                    lock_keys=[*lock, *updates])
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

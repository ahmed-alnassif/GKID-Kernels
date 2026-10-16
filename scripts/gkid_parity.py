#!/usr/bin/env python3
"""GKID parity for 6.1 sublevels that are plain android14-6.1-lts commits.

Only the GKID-6.1 tip carries Ahmed Al-Nassif's GKID patch stack. Older pinned
sublevels are plain android14-6.1-lts commits and lack it, notably:
  - the removal of android/abi_gki_protected_exports_* (otherwise the phone's
    Google-signed GKI modules may not export protected symbols: Wi-Fi and other
    functions break),
  - forced loading of modules whose symbol CRCs differ,
  - the performance patches.
Cogan already carries the same stack as kernel-patches/common (used for the other
ACK versions). This module applies it, strictly (plain git apply, no fuzz), so the
result can be locked as a tree.

The stack is present when kernel/module/version.c has the force-load message.

The rothko stock kernel source (official ACK, not GKID) gets only the compatibility
part (compat=True): module force-load and the removal of the protected exports. It
stays as close to the stock kernel as possible: the GKID performance patches change
KMI types (e.g. 0005 aligns struct file) and two of them do not apply there.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_DIR = ROOT / "kernel-patches/common"
VERSION_C = "kernel/module/version.c"
MARKER = re.compile(r"disagrees about version of symbol.*but ignore")
PROTECTED = "android/*protected_exports*"
FORCE_LOAD = "0003-kernel-module.c-Force-loading-of-modules-that-fail-s.patch"


def patches():
    """The GKID-equivalent patches in apply order (zero-padded names, like sort -V)."""
    found = sorted(PATCH_DIR.glob("*.patch"))
    if not found:
        raise ValueError(f"no GKID-equivalent patches in {PATCH_DIR}")
    return [(path.name, path.read_bytes()) for path in found]


def has_stack(text):
    return bool(MARKER.search(text))


def git(repo, *args, env=None, data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                            env=env, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: "
                           + result.stderr.decode(errors="replace").strip()[:1500])
    return result.stdout.decode().strip()


def apply(repo, cached=False, env=None, compat=False):
    """Apply the stack to the work tree (or only the index) and drop the protected exports.

    compat: only the module force-load patch (stock ACK sources)."""
    mode = ["--cached"] if cached else []
    for name, raw in patches():
        if compat and name != FORCE_LOAD:
            continue
        try:
            git(repo, "apply", *mode, "--check", "-", env=env, data=raw)
            git(repo, "apply", *mode, "-", env=env, data=raw)
        except RuntimeError as exc:
            raise RuntimeError(f"GKID parity patch {name} does not apply: {exc}") from None
    listed = git(repo, "ls-files", "--", PROTECTED, env=env).splitlines()
    if not listed:
        raise RuntimeError("no android/*protected_exports* file to remove")
    git(repo, "rm", "-q", *mode, "--", *listed, env=env)
    return listed

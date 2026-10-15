#!/usr/bin/env python3
"""Read-only root manager ref provenance. Does not install or update drivers.

Usage: python3 scripts/collect_root_provenance.py [output.json]
Network failures are recorded as unresolved, never fabricated as installed SHAs.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAMS = {
    "KSUN": ("https://github.com/KernelSU-Next/KernelSU-Next.git", None),
    "KSU": ("https://github.com/tiann/KernelSU.git", "refs/heads/main"),
    "BSU": ("https://github.com/Baka-SU/BakaSU.git", "refs/heads/main"),
}

def ksun_build_reference():
    source = (ROOT / "build.sh").read_text(encoding="utf-8")
    refs = re.findall(r'^\s*KSUN_REF="([^"\n]+)"\s*$', source, re.MULTILINE)
    pins = re.findall(r'^\s*KSUN_EXPECTED_SHA="([0-9a-f]{40})"\s*$', source, re.MULTILINE)
    if len(refs) != 1 or len(pins) != 1:
        raise ValueError("Missing or ambiguous KSUN tag/immutable pin in build.sh")
    return "refs/tags/" + refs[0], pins[0]

def resolve(url, ref):
    if not ref.startswith(("refs/heads/", "refs/tags/")):
        return None, "An exact branch or tag ref is required"
    patterns = [ref]
    if ref.startswith("refs/tags/"):
        patterns.append(ref + "^{}")
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", url, *patterns],
            check=True, capture_output=True, text=True, timeout=20,
        )
        matches = {}
        for line in result.stdout.splitlines():
            sha, name = line.split("\t", 1)
            if name in patterns and re.fullmatch(r"[0-9a-fA-F]{40}", sha):
                matches[name] = sha.lower()
        # Annotated tags resolve to the commit, not the tag object.
        sha = matches.get(ref + "^{}") or matches.get(ref)
        if sha:
            return sha, None
        return None, "No exact matching ref SHA in ls-remote response"
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__

def collect():
    items = {}
    try:
        ksun_ref, ksun_pin = ksun_build_reference()
        ksun_error = None
    except (OSError, ValueError) as exc:
        ksun_ref, ksun_pin = None, None
        ksun_error = str(exc)
    for name, (url, ref) in UPSTREAMS.items():
        expected = ksun_pin if name == "KSUN" else None
        if name == "KSUN":
            ref = ksun_ref
        sha, error = resolve(url, ref) if ref else (None, ksun_error)
        matches_pin = sha == expected if sha and expected else None
        if matches_pin is False:
            error = "Remote tag differs from immutable Cogan build pin; review required"
        items[name] = {
            "repository": url,
            "requested_ref": ref.rsplit("/", 1)[-1] if ref else None,
            "git_ref": ref,
            "resolved_ref_sha": sha,
            "expected_build_sha": expected,
            "matches_build_pin": matches_pin,
            "installed_source_sha": None,
            "patchset_sha": None,
            "resolution_error": error,
        }
    return {
        "schema_version": 2,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Observed remote refs only. KSUN uses the tag and immutable pin from build.sh; other managers use branch tips. Not proof of installed source or Manager APK compatibility.",
        "root_managers": items,
    }

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    data = json.dumps(collect(), indent=2, sort_keys=True) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    else:
        sys.stdout.write(data)

if __name__ == "__main__":
    main()

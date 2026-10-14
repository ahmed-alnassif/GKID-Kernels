#!/usr/bin/env python3
"""Read-only root manager ref provenance. Does not install or pin drivers.

Usage: python3 scripts/collect_root_provenance.py [output.json]
Network failures are recorded as unresolved, never fabricated as installed SHAs.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UPSTREAMS = {
    "KSUN": ("https://github.com/KernelSU-Next/KernelSU-Next.git", "next"),
    "KSU": ("https://github.com/tiann/KernelSU.git", "main"),
    "BSU": ("https://github.com/Baka-SU/BakaSU.git", "main"),
}

def resolve(url, ref):
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", url, f"refs/heads/{ref}"],
            check=True, capture_output=True, text=True, timeout=20,
        )
        for line in result.stdout.splitlines():
            sha, name = line.split("\t", 1)
            if name == f"refs/heads/{ref}" and len(sha) == 40 and all(c in "0123456789abcdef" for c in sha.lower()):
                return sha.lower(), None
        return None, "No exact matching branch SHA in ls-remote response"
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__

def collect():
    items = {}
    for name, (url, ref) in UPSTREAMS.items():
        sha, error = resolve(url, ref)
        items[name] = {
            "repository": url,
            "requested_ref": ref,
            "resolved_ref_sha": sha,
            "installed_source_sha": None,
            "patchset_sha": None,
            "resolution_error": error,
        }
    return {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Observed remote branch tips only; not proof of installer-selected source or Manager APK compatibility.",
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

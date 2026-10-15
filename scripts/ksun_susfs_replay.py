#!/usr/bin/env python3
"""Strict, isolated patch replay for a KSUN+SUSFS candidate.

Manifest JSON:
{"kernel_commit":"<40 hex chars>","patches":[{"path":"patches/001.patch","sha256":"<64 hex chars>"}]}
Paths are relative to the manifest directory. Defaults to verification only.
No downloads, builds, production workflow changes, or fuzzy patching.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def git(tree, *args):
    return subprocess.run(["git", "-C", str(tree), *args],
                          check=True, capture_output=True, text=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="Apply verified patches; default only verifies inputs")
    args = parser.parse_args()
    try:
        tree = args.kernel.resolve(strict=True)
        manifest = args.manifest.resolve(strict=True)
        if not (tree / ".git").exists():
            raise ValueError("kernel must be a Git checkout/worktree root")
        if Path(git(tree, "rev-parse", "--show-toplevel").stdout.strip()).resolve() != tree:
            raise ValueError("kernel must be the checkout root")
        if git(tree, "status", "--porcelain", "--untracked-files=all").stdout.strip():
            raise ValueError("kernel checkout is dirty; refusing replay")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        expected_head = data.get("kernel_commit")
        if not isinstance(expected_head, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_head):
            raise ValueError("manifest requires immutable kernel_commit SHA")
        actual_head = git(tree, "rev-parse", "HEAD").stdout.strip()
        if actual_head != expected_head:
            raise ValueError(f"kernel HEAD mismatch: expected {expected_head}, got {actual_head}")
        patches = data.get("patches")
        if not isinstance(patches, list) or not patches:
            raise ValueError("manifest must have a nonempty patches list")
        resolved = []
        for entry in patches:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError("invalid patch entry")
            expected = entry.get("sha256")
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError("missing or invalid SHA256")
            path = (manifest.parent / entry["path"]).resolve(strict=True)
            if not path.is_relative_to(manifest.parent) or not path.is_file():
                raise ValueError("patch path escapes manifest directory")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("patch checksum mismatch: " + str(path))
            resolved.append((path, raw))
        print(f"Verified {len(resolved)} patch checksums and clean kernel checkout.")
        if not args.apply:
            print("VERIFY ONLY: no patch applied. Use --apply for strict sequential replay.")
            return 0
        for index, (path, raw) in enumerate(resolved, 1):
            # No --3way, no --reject, no fuzz, no shell pipeline.
            for action in (["apply", "--check", "-"], ["apply", "-"]):
                result = subprocess.run(["git", "-C", str(tree), *action],
                                        input=raw, capture_output=True, timeout=60)
                if result.returncode:
                    raise RuntimeError(f"patch {index} ({path.name}) failed: "
                                       + result.stderr.decode(errors="replace")[:2000])
            print(f"Applied {index}/{len(resolved)}: {path.name}")
        print("PATCH REPLAY COMPLETE; full Image and runtime remain unverified.")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError, RuntimeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

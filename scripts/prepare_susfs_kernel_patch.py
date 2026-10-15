#!/usr/bin/env python3
"""Prepare the pinned SUSFS kernel patch from a locally obtained original.

Offline, fail-closed: no downloads, no kernel-tree mutation, no build.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path, help='Original SUSFS 6.1 patch from pinned GitLab commit')
    parser.add_argument('output', type=Path, help='New file path for adjusted kernel patch')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    lock = json.loads((root / 'configs/ksun-susfs-6.1.lock.json').read_text())
    adaptation = lock['adaptation']
    delta = root / adaptation['delta']
    try:
        if not args.original.is_file() or not delta.is_file():
            raise ValueError('Original SUSFS patch or locked delta is missing')
        if digest(args.original) != adaptation['input_sha256']:
            raise ValueError('Original SUSFS patch SHA256 mismatch')
        if digest(delta) != adaptation['delta_sha256']:
            raise ValueError('Companion delta SHA256 mismatch')
        output = args.output.resolve()
        if output.exists():
            raise ValueError('Output already exists; refusing overwrite')
        if output == args.original.resolve() or output == delta.resolve():
            raise ValueError('Output must be a separate file')
        if not output.parent.is_dir():
            raise ValueError('Output directory does not exist')
        with tempfile.TemporaryDirectory(prefix='susfs-patch-') as tmp:
            source = Path(tmp) / adaptation['applies_to']
            source.parent.mkdir(parents=True)
            source.write_bytes(args.original.read_bytes())
            for action in ('--check', ''):
                cmd = ['git', '-C', tmp, 'apply']
                if action:
                    cmd.append(action)
                cmd.append(str(delta))
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise ValueError('Companion adjustment rejected: ' + result.stderr[:1200])
            if digest(source) != adaptation['output_sha256']:
                raise ValueError('Adjusted SUSFS patch SHA256 mismatch')
            # Exclusive create: never overwrite an output that appeared during preparation.\n            with output.open('xb') as target:\n                target.write(source.read_bytes())
        print('VERIFIED: original, delta, and adjusted patch SHA256 match lock')
        print('OUTPUT:', output)
        print('NOT APPLIED to kernel; full build and runtime unverified')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('BLOCKED:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

# KSUN + SUSFS 6.1 — isolated configuration preflight

Status: **BLOCKED until pinned integrated kernel source and toolchain are present**. This is a source/config-only procedure, **not** authorization to compile, release, flash, dispatch Actions, or change production guards.

## Locked identities

- Repository: `cogan17/Cogan`, branch `dev`.
- Core kernel tree: `7e2b5164757d23fe0fbe3cd81ebec264769a0542`.
- Integrated feature kernel tree: `b5db2f3ccc53539083461caa5cb7d1ddb5cd9e81`.
- KSUN tree: `2fd43a2d0ef0e1750102348869dd1152d306afb1`.
- Feature fragment SHA256: `792f1fa18bd85696c94918a5b3175e0baf54a336f66af0c41e1dbc9bb133d1c9`.
- Neutron release: `06092026`, archive SHA256: `531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30`.

## Prerequisites (stop if any fail)

1. Locate the original isolated integrated worktree. Do **not** replay core or feature patches on an already-integrated tree. If missing, reconstruct once using the existing pinned core/feature replay records, in a separate disposable workspace; never mutate preserved core inputs.
2. The original feature worktree is intentionally **staged but not committed**. Verify `git rev-parse HEAD` equals the frozen core snapshot `3f08838cbc5a94bf877df6a462dabb9118095314`, then verify `git write-tree` equals the integrated feature tree `b5db2f3ccc53539083461caa5cb7d1ddb5cd9e81`. Do **not** compare `HEAD^{tree}` with the feature tree: HEAD still points at the core snapshot. Confirm `git diff --quiet` (no unstaged changes), `git ls-files --others --exclude-standard` is empty, and compare `git diff --cached --binary HEAD | sha256sum` with the staged diff SHA256 `c06e6132e8a665b7db9a3a9be52fca22d23405fa2d99b546842d232a3c39f54f` from the stage manifest. Stop on mismatch; never reset or restage the worktree merely to satisfy this gate.
3. Verify the exact Neutron archive SHA256 and extracted clang/LLD identities, host dependencies (including `bc`, `bison`, `flex`, `pahole`) and their runtime paths. A different system clang is not an acceptable substitute.
4. Verify `sha256sum configs/ksun-susfs-6.1-features.config` matches the locked checksum. Do not import shared `configs/features.config` (it contains NTSync).
5. Verify the lock's `guards` remain false: `production_enabled`, `run_full_build`, `release_allowed`, `flash_allowed`, `lkm_allowed`.

## Configuration-only procedure

In a **new empty** `O=` directory, run `gki_defconfig` using the pinned kernel tree and toolchain. Merge **only** `configs/ksun-susfs-6.1-features.config` using the locked `scripts/kconfig/merge_config.sh -m` method, then run `olddefconfig` with the same toolchain and isolated output directory. Record exact commands, environment, and tool versions. Do not reuse old `.config`, `features.config`, or ThinLTO cache.

Then execute:

```sh
python3 scripts/check_ksun_susfs_resolved_config.py /absolute/path/to/new/out/.config
sha256sum /absolute/path/to/new/out/.config
```

The validator must pass all locked enabled and disabled flags, KSUN/SUSFS, BBG, NoMount, Full LTO/CFI, KEYS, ARM64, and the `baseband_guard` LSM token. Inspect the generated config for unwanted NTSync, DroidSpaces, or LKM settings. Save the final config checksum and source/toolchain identities in a new validation record **only after actual execution**.

## Current evidence and boundaries

The offline validator test suite passed 15 tests on 2026-10-15, and the pinned fragment hash matched. The offline CLI smoke test used a synthetic configuration, **not** a Kconfig-resolved kernel configuration. Direct GitHub cloning in the current environment failed DNS resolution, and the prior Work integrated worktree is not mounted here. Consequently **no genuine `olddefconfig` output exists and compilation readiness is NOT established**.

No additional Actions, PRs, builds, releases, or flashes are required for this preflight document.

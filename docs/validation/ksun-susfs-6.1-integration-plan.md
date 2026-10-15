# KSUN + SUSFS 6.1 — isolated candidate plan

Status: **INCOMPLETE / DO NOT BUILD OR FLASH**.
Scope: cogan17/Cogan branch dev, GKI Android 14 / kernel 6.1.
This is a plan, not a verified replay or build result.

## Source locks
- Kernel: `a7ba124af5a535078d3f83b3e145f9cc8ec651b8`
- KSUN (pershoot): `2f858cb292265795dee2807759cec2eb8a7d79b1`
- SUSFS historical lock (unavailable in owner's fetched Git object set): `a9bb4dd3ed248ada636b480bfdff70af704f1463`
- **Verified file provenance**: `92aab7f579e9fb440a43e387c13bff519af13462` supplies four matching SHA256 files. This is a source-file provenance finding, not an automatic replacement for the historical lock.
- Evidence inventory: `docs/validation/ksun-susfs-6.1-replay-manifest.json`

## Required sequence (not yet executed)
1. Create a disposable clean kernel checkout at the exact kernel SHA; assert HEAD.
2. Obtain the exact KSUN and SUSFS commits; assert HEAD and clean status. Never run a floating `setup.sh` or a pull/stash fallback.
3. Inventory remaining prerequisite kernel modifications (BBG, NoMount) and their ordered patches; NTSync is explicitly excluded following its removal from build.sh and functions.sh. Lock their bytes and SHA256. Existing upstream commit references are provenance, not verified patches.
4. Reproduce KSUN driver integration in the isolated tree only: symlink `drivers/kernelsu` to the pinned KSUN kernel directory, then add the Kbuild and Kconfig entries only if absent. Verify paths and diff.
5. Verify SUSFS companion file SHA256 before copying to `fs/susfs.c`, `include/linux/susfs.h`, and `include/linux/susfs_def.h`.
6. Verify the original SUSFS kernel patch and companion adjustment hashes, generate the prepared patch, then check its recorded hash and run strict patch preflight on the exact candidate tree.
7. Record a complete ordered replay manifest with local patch paths, source revisions and SHA256. The current evidence inventory is NOT compatible with `scripts/ksun_susfs_replay.py`.
8. Lock toolchain archive URL and downloaded bytes; record exact kernel configuration inputs and generation commands.
9. Run isolated compile/link checks, then one full Image build only after all preflights pass. Inspect first failure; avoid repetitive Actions.
10. Verify artifacts and device compatibility before any release or flashing. Runtime is a separate gate.

## Current blockers
- Complete ordered patch series and historical candidate working-tree diff unavailable. Four SUSFS source files have matching hashes, but this does not establish full replay.
- Exact KSUN+SUSFS integrated source tree not independently verified.
- BBG executes a floating upstream setup script in `build.sh`; pin and verify its transitive inputs for reproducible candidate builds. NTSync must not be reintroduced.
- Toolchain and .config provenance not locked.

## Production safety
- Keep KSUN v3.4.2 production path unchanged.
- Keep KSUN+SUSFS workflow guard enabled.
- No LKM SUSFS, release, flashing, or production switch until verified.
- No new CI run or PR merely to validate this documentation.

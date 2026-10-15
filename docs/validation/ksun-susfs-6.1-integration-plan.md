# KSUN + SUSFS 6.1 — isolated candidate plan

Status: **INCOMPLETE / DO NOT BUILD OR FLASH**.
Scope: cogan17/Cogan branch dev, GKI Android 14 / kernel 6.1.
This is a plan, not a verified full replay or build result. The source-contract review and offline preparer are now recorded in `ksun-susfs-6.1-api-review.md`; use the separate v2 candidate lock for uploaded companion bytes.

## Source locks
- Kernel: `a7ba124af5a535078d3f83b3e145f9cc8ec651b8`
- KSUN (pershoot): `2f858cb292265795dee2807759cec2eb8a7d79b1`
- SUSFS historical lock (unavailable in owner's fetched Git object set): `a9bb4dd3ed248ada636b480bfdff70af704f1463`
- **Uploaded file provenance**: prior owner evidence attributes the uploaded files to `92aab7f579e9fb440a43e387c13bff519af13462`. Three of four hashes match the historical manifest; `susfs.c` differs. The separately reviewed candidate v2 explicitly locks its observed `5521aa60...` checksum without replacing the historical lock. No fresh upstream GitLab checkout was verified in this review.
- Evidence inventory: `docs/validation/ksun-susfs-6.1-replay-manifest.json`

## Required sequence (not yet executed)
1. Prepare the v2 bundle with `scripts/prepare_ksun_susfs_candidate.py`; then obtain disposable clean sibling `kernel` and `ksun` checkouts at their exact SHAs. KSUN must be nonshallow. The historical workspace is unavailable.
2. Obtain the exact KSUN and SUSFS commits; assert HEAD and clean status. Never run a floating `setup.sh` or a pull/stash fallback.
3. Inventory remaining prerequisite kernel modifications (BBG, NoMount) and their ordered patches; NTSync is explicitly excluded following its removal from build.sh and functions.sh. Lock their bytes and SHA256. Existing upstream commit references are provenance, not verified patches.
4. Reproduce KSUN driver integration in the isolated tree only: symlink `drivers/kernelsu` to the pinned KSUN kernel directory, then add the Kbuild and Kconfig entries only if absent. Verify paths and diff.
5. Use the explicit candidate-v2 companion hashes (not the unresolved historical `susfs.c` hash); verify SHA256 before copying to `fs/susfs.c`, `include/linux/susfs.h`, and `include/linux/susfs_def.h`.
6. Verify the original SUSFS kernel patch and companion adjustment hashes, generate the prepared patch, then check its recorded hash and run strict patch preflight on the exact candidate tree.
7. The preparer generates a distinct `kernel-replay.json` containing the driver patch then prepared main SUSFS patch with local paths and SHA256. This is a minimal source-stage series; finish the locked BBG/NoMount feature series separately before claiming full replay. The evidence inventory is NOT compatible with `scripts/ksun_susfs_replay.py`.
8. Lock toolchain archive URL and downloaded bytes; record exact kernel configuration inputs and generation commands.
9. Run isolated compile/link checks, then one full Image build only after all preflights pass. Inspect first failure; avoid repetitive Actions.
10. Verify artifacts and device compatibility before any release or flashing. Runtime is a separate gate.

## Current blockers
- Complete ordered patch series and historical candidate working-tree diff unavailable. Three of four uploaded files match the historical manifest. Candidate v2 locks all four uploaded file hashes separately; this does not recover the historical dirty tree or full feature replay.
- Exact full KSUN+SUSFS integrated source tree not independently verified. The offline bundle was prepared; optional real-checkout staging is pending. The new driver patch passed only a pinned two-file fixture check.
- BBG executes a floating upstream setup script in `build.sh`; pin and verify its transitive inputs for reproducible candidate builds. NTSync must not be reintroduced.
- Toolchain and .config provenance not locked.

## Production safety
- Keep KSUN v3.4.2 production path unchanged.
- Keep KSUN+SUSFS workflow guard enabled.
- No LKM SUSFS, release, flashing, or production switch until verified.
- No new CI run or PR merely to validate this documentation.

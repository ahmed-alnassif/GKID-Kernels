# KSUN + SUSFS 6.1 — Work handoff checkpoint (2026-10-15)

**Status: selected source API contracts PASS; isolated v2 bundle PREPARED; full source stage and compilation BLOCKED. DO NOT BUILD, RELEASE, OR FLASH.** Resume with **Lanjutkan** on `cogan17/Cogan`, branch `dev`. Only built-in KSUN + kernel-patched SUSFS is selected. Production KSUN and both KSUN+SUSFS guards remain unchanged.

## Completed evidence — reuse, do not repeat

- Kernel lock: `a7ba124af5a535078d3f83b3e145f9cc8ec651b8`; KSUN: `pershoot/KernelSU-Next@2f858cb292265795dee2807759cec2eb8a7d79b1`.
- Existing successful main-patch apply check: Actions run `38691986084`, job `116279761088`. Not rerun. Original SUSFS patch SHA256 `57e97f34055608a133594ff723ae5fa436b4559b1473d6e3284093c3ccb22156`, adjustment `6962a4a910ef74c776e7793cf64a064712fd26d71f90529208adbf35d9d88af1`, prepared patch `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b` remain unchanged.
- Selected API contracts reviewed against immutable KSUN blobs and uploaded SUSFS bytes: `ksu_cred`, three-argument SUSFS `ksu_handle_setresuid`, three-argument adjusted `ksu_handle_sys_read`, `ksu_is_init_rc_hook_enabled`, `susfs_init`, work/SID/SELinux dependencies, syscall hooks, dispatch commands and namespace/statfs helpers. No actual mismatch found in these contracts. Details and limits: `docs/validation/ksun-susfs-6.1-api-review.md`. This is not compiler/link/runtime validation.
- Historical SUSFS lock `a9bb4dd3ed248ada636b480bfdff70af704f1463` remains unresolved and unchanged. Historical `susfs.c` hash `976f6d47a45260bcb0bb17d8ffe8beddeda398f8aba9bba54517ece9daf9e253` is preserved. Uploaded patch and two headers match historical hashes; `susfs.c` does not. Do not claim a historical 4/4 match.
- Explicit new source selection: `configs/ksun-susfs-6.1-candidate-v2.json` locks uploaded `susfs.c` hash `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7` separately. Prior owner evidence attributes the bytes to `simonpunk/susfs4ksu@92aab7f579e9fb440a43e387c13bff519af13462`; no fresh upstream checkout was verified here. Archive `susfs-verified.zip` is Library file `libfile_c30e8e90578881918254394efb95d610`, archive SHA256 `4308a05c09462c22edf390be066c5e31503de8585891fd2829533c71cbed0777`.
- `scripts/prepare_ksun_susfs_candidate.py` successfully prepared the real v2 bundle from that archive. It verifies exact ZIP members, member hashes, original/delta/prepared hashes and new driver patch. Generated `kernel-replay.json` orders driver integration then prepared SUSFS kernel patch; companion copies are separately locked. The evidence inventory JSON is not an executable replay manifest.
- New driver patch SHA256 `01f05f137353ad14823da02f9aeaedf981b83a7f07e2b2327b6d379af4362149` passed a strict check/application on a two-file fixture from pinned kernel driver Makefile/Kconfig blobs. **Not a complete kernel replay.** Layout requires adjacent isolated `kernel` and `ksun` checkouts; symlink is `drivers/kernelsu -> ../../ksun/kernel`.
- Ten new offline candidate preparation/staging/rejection tests passed, including successful synthetic staging and later-patch rejection leaving the kernel clean. Root matrix/early guard assertions and Python syntax passed. No new Actions, PR, Image build, release, flash, LKM, or production switch.

## Current boundary

The historical workspace `/workspace/scratch/a01fce1f8f50` is absent. Its old successful partial objects/config cannot be recovered by inventing empty directories or substituting HEADs. Optional staging has passed synthetic tests only; complete real kernel/KSUN checkouts have not been staged here. Toolchain bytes/URL, exact config generation and final feature replay remain unverified.

## Next exact work

1. Reuse the API review, archive and v2 lock. Obtain or reuse complete clean pinned kernel and KSUN checkouts without redundant downloads. KSUN must be **nonshallow** because Kbuild can fetch `--unshallow`; no floating setup/pull/stash or fallback scripts. Keep independent isolated paths.
2. Run `scripts/prepare_ksun_susfs_candidate.py /path/to/susfs-verified.zip /isolated/new-bundle --kernel /isolated/kernel --ksun /isolated/ksun` with a new output path. It checks roots/HEADs/cleanliness and empty destinations; existing replay preflights the entire series in a disposable index before application. Preserve first failure and diagnostics. Do not rerun the green main-patch-only Actions check.
3. Finish SHA-locked BBG + NoMount replay for the intended feature bundle; NTSync excluded, DroidSpaces disabled. The two-patch bundle is minimal KSUN+SUSFS source integration and does not stand in for the full feature candidate.
4. Resolve KSUN version metadata against the immutable `v3.4.2` base, pin toolchain URL + archive bytes/SHA256, record exact config inputs/generation commands, select clean LTO, and verify resolved `CONFIG_KSU=y`, `CONFIG_KSU_SUSFS=y`, `CONFIG_THREAD_INFO_IN_TASK=y` and required ARM64/KPROBES settings.
5. Only after real source-stage/config/toolchain preflights pass, consider one selective compile/link then Image attempt. Inspect first failure before any rerun. Full Image, KCFI/ABI/KMI, manager and runtime are separate gates. Tell the owner when the compilation gate actually becomes ready.

## Rules retained

- No repeated successful CI, speculative PR, checkpoint spam, or redundant cloning; maximum one justified retry after diagnosis.
- Owner manually triggers workflow/releases; no automatic upstream updates.
- No SUSFS LKM, production guard removal, release or flash. Preserve original patches and historical evidence. Never apply the namespace fix twice; the locked adjustment already includes it.
- Evidence inventory: `docs/validation/ksun-susfs-6.1-replay-manifest.json`; executable replay manifest is generated separately. Historical partial build stays in its original record and does not prove the new candidate.

# KSUN + SUSFS 6.1 — Work handoff checkpoint (2026-10-15)

**Status: OWNER STOPPED at 2026-10-15 14:41 WIB. V2 CORE + BBG/NOMOUNT SOURCE STAGED. NOT READY FOR COMPILATION, RELEASE OR FLASH.**
Resume with **Lanjutkan**. Repository `cogan17/Cogan`, branch `dev`. Built-in
**KernelSU Next + kernel-patched SUSFS** only. Production KSUN and both
KSUN+SUSFS guards remain unchanged. No Actions dispatch or new PR this session.

## Completed — do not repeat
- Exact kernel `a7ba124af5a535078d3f83b3e145f9cc8ec651b8` and KSUN `2f858cb292265795dee2807759cec2eb8a7d79b1` independently checked out.
- Full source-level API review completed: `ksu_cred`, three-argument SUSFS `ksu_handle_setresuid`, three-argument `ksu_handle_sys_read`, `ksu_is_init_rc_hook_enabled`, `susfs_init`, SELinux and other patch providers, namespace helpers, and all 14 command handlers match their consumers after the existing locked read-hook adjustment. Definitions, config branches and linkage evidence are in `ksun-susfs-6.1-api-review.md`. This is not compiler/link/runtime proof.
- Four uploaded files preserved byte-for-byte in `kernel-patches/susfs/6.1-v2/source/`. Original patch and headers match historical expected hashes; `susfs.c` candidate is `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7`, different from historical `976f6d47a45260bcb0bb17d8ffe8beddeda398f8aba9bba54517ece9daf9e253`.
- Explicit new candidate v2 chosen after API review; historical source lock `a9bb4dd3ed248ada636b480bfdff70af704f1463`, expected checksum and partial-build JSON remain intact. Owner-reported source revision `92aab7f579e9fb440a43e387c13bff519af13462` was not independently fetched this session. The cause/content delta of the historical checksum discrepancy remains unknown; no silent substitution or four-of-four historical match claim.
- One local complete core-source integration succeeded in new detached worktrees: driver wiring, prepared kernel patch, and checksum-verified companions. Three kernel patches passed whole-series index preflight and strict sequential replay without fuzz. This extends the prior successful main-patch-only check; that green Action was not rerun.
- One candidate-only KSUN Kbuild patch removes implicit Git fetching and fixes offline version metadata. Complete local KSUN history has 3365 reachable commits; nearest tag v3.4.2 is `4c706b5938665866ebe16944a481a7b91e3396af`; KSU version is 33365.
- Integrated kernel tree: `7e2b5164757d23fe0fbe3cd81ebec264769a0542`; KSUN tree: `2fd43a2d0ef0e1750102348869dd1152d306afb1`. Five worktree preparation tests initially passed; the concurrent archive interface and its ten tests are preserved in the same script and suite. Python syntax checked. No kernel compilation was started.

Concurrent commit `7dcdef0` was incorporated without overwriting it. The original ZIP preparation interface and its ten tests remain available. Use **--locked-worktrees** for this recorded source stage. The archive lock `configs/ksun-susfs-6.1-candidate-v2.json` and worktree lock `configs/ksun-susfs-6.1-v2.lock.json` have distinct roles for the same selected source set.

## Latest stop checkpoint — 2026-10-15 14:41 WIB

Owner explicitly requested stopping here. No further configuration, compilation, test, download retry or Actions was started after that request. The checkpoint threshold is now **credit below 8%**, replacing the former 10% threshold. There is no automatic credit-percentage readout; only a real indicator or owner notice can trigger it. This stop is the owner's instruction, not a claimed quota measurement.

- Remote concurrent core work was saved as `3ccaea594f54d2e0ca9b8d2ee8b7946254f588c6` and reused. Its resolved merge and successful core replay were not repeated.
- New feature continuation is `/workspace/scratch/466d29bc15a5/candidate-feature`, with `kernel` and `ksun` worktrees. Core input kernel tree `7e2b5164757d23fe0fbe3cd81ebec264769a0542`, KSUN tree `2fd43a2d0ef0e1750102348869dd1152d306afb1` were independently matched to the recorded tree/diff evidence before reuse. Frozen core snapshot commits and reconstruction identities are in `ksun-susfs-6.1-features-stage.json`.
- BBG `a54e0dc6cf0aff4dd87fec49644a02d2eb612905` and NoMount `7046c7ad3ee0bf4ae66e80f6b93b1e30db0cb4e3`: 17 source files checked against pinned Git blobs and SHA256; installers were reviewed, never executed. Candidate Makefiles use fixed offline metadata instead of Git fetching/queries. Two new feature patches passed full-series disposable-index preflight and strict actual replay once. Feature kernel tree is `b5db2f3ccc53539083461caa5cb7d1ddb5cd9e81`.
- Feature lock: `configs/ksun-susfs-6.1-features.lock.json`; helper: `scripts/prepare_ksun_susfs_features.py`; emitted patches and replay manifest: `kernel-patches/susfs/6.1-v2/features/`. This extends the recorded core; do not apply those patches again to the current staged tree.
- Exact compiler archive downloaded once: release `06092026`, SHA256 `531083928c8e37f6b31e324dbfd0b5a8323f989b1c57ff2c1368b889b5b1bd30`, LLVM `f42c87ba2c70219b1f4ad1f031a5b6a1ea6603fb`. URL and asset identity are locked. All 316 extracted regular-file contents and symlink targets were compared with the archive after ownership-only tar warnings. Clang/LLD identity commands succeeded. Local compiler root: `/workspace/scratch/466d29bc15a5/toolchains/neutron-06092026`.
- Nine Ubuntu host-tool/library packages were SHA256 verified and unpacked under `/workspace/scratch/466d29bc15a5/host-tools/root`; bc/bison/flex/pkgconf version commands succeeded. No system package installation. `pahole` remains missing: its first package download failed with a proxy CONNECT timeout. Exact pending package URL/SHA256 and dependencies are recorded; no retry after owner stop.
- `configs/ksun-susfs-6.1-features.config` is an **unresolved fragment** selecting KSUN/SUSFS/BBG/NoMount, Full LTO/CFI, KEYS and the BBG LSM token, excluding NTSync. No output `.config` was generated, no kernel object/Image was compiled, and no new feature-helper unit tests were run before the stop. DroidSpaces/SUSFS LKM remain excluded. Shared `configs/features.config` still requests NTSync and must not be imported.

## Exact continuation

1. Read `docs/validation/ksun-susfs-6.1-features-stage.json` and this latest section first. Reuse the actual staged feature worktrees and compiler when present. Preserve the clean original source inputs and earlier core stage at `/workspace/scratch/d5d3c6fbcebc`; do not reset them, clone again, rerun green checks, or replay the core/features onto patched worktrees.
2. Finish only the pending `pahole` retrieval and host dependency preparation, using the recorded exact package metadata. Diagnose the prior proxy CONNECT failure before one justified retry. Do not use apt installation or floating installers.
3. Generate a new config in the **fresh** `/workspace/scratch/466d29bc15a5/candidate-feature/out` directory. Pin environment/commands for `gki_defconfig`, merge the locked feature fragment, then `olddefconfig`. Record final `.config` SHA256 and check required flags, Full LTO/CFI, BBG LSM, KEYS, NoMount and exclusions. Never reuse the historical config or ThinLTO cache. Local bison requires its extracted data path; record host PATH/library/pkgconf paths as well.
4. Selectively verify newly changed helpers and complete compilation preflight. Only when source, toolchain, host and resolved-config gates pass, tell the owner that an isolated compilation can start. Production KSUN+SUSFS remains blocked; Image/link/KCFI/ABI/KMI, manager and runtime remain unverified.
5. If transient workspaces are missing, reconstruct once from the committed core replay and feature patches plus the recorded deterministic frozen-core commit metadata. The executable feature manifest expects that frozen core HEAD. Do not confuse it with the old evidence inventory JSON.

## Preserved evidence and rules
- Historical lock: `configs/ksun-susfs-6.1.lock.json`; partial build: `ksun-susfs-6.1-partial-build.json`; old evidence inventory: `ksun-susfs-6.1-replay-manifest.json`. None certifies the new v2 build.
- Original patch SHA256 `57e97f34055608a133594ff723ae5fa436b4559b1473d6e3284093c3ccb22156`; adjustment `6962a4a910ef74c776e7793cf64a064712fd26d71f90529208adbf35d9d88af1`; prepared patch `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b`.
- Historical main-patch-only pass: run `38691986084`, job `116279761088`. Reuse it; no redundant CI. The older evidence inventory is NOT accepted by replay.py; use the new schema-correct replay manifests.
- No NTSync, DroidSpaces or SUSFS LKM. No floating setup.sh, pull/stash/fuzz, automatic fallback or upstream update. No production guard removal.
- No duplicate work/downloads, speculative PRs, repeated successful Actions or checkpoint spam. Owner manually initiates builds/releases. NoMount + clean LTO remains the requested bundle direction. Update this checkpoint selectively.

Post-merge validation: ten archive-interface tests and five offline worktree tests passed. Only the affected five were rerun after correcting a helper-name merge error. The already successful complete core-source replay was not repeated.

## Checkpoint 2026-10-15 — BBG candidate isolated (latest handoff)

- Scope: branch `dev`, KSUN + SUSFS kernel 6.1 with locked BBG/NoMount feature staging. Earlier successful source checks and Actions remain evidence; do not repeat them.
- New isolated candidate: `kernel-patches/susfs/6.1-v2/candidates/bbg-allow-cache-spinlock.patch`, commit `78c97de84e714b37a00d4b3e9980611c7f5b67d9`. Fix targets unsynchronized `allowed_devs` hashtable: one IRQ-safe spinlock for readers/insertion, double-check under lock, allocation/free and logging outside lock. Candidate is **not** included in `features/kernel-replay.json` or any build.
- Source-only patch hunk check: original BBG source reconstructed from locked `features/001-bbg.patch` has 270 lines; candidate hunk context matches exactly (32 old / 55 new), resulting source 293 lines. This is not a full kernel compile or runtime concurrency test.
- **Evidence limitation (resolved 2026-10-15):** exact-file `git apply --check` was executed and passed; see *BBG candidate exact-file check* below.
- Immutable inputs: `features/001-bbg.patch`, `features/002-nomount.patch`, locked manifests, pinned commits/checksums, production guards. Do not modify without a separate reviewed/versioned decision. No manual Actions, PR, build, release or flash was performed for this candidate.
- Next action: owner decision on integrating the candidate (see below). Full pinned kernel/toolchain and resolved config gates remain pending; **not ready for compilation or production**.
- Owner continuation: reply `Lanjutkan`. Minimize GitHub calls, checkpoints, duplicate tests and documentation churn; stop and checkpoint when user requests or remaining credits approach the agreed threshold (credit percentage cannot be read automatically here).

## BBG candidate exact-file check — 2026-10-15

Disposable git tree (empty base commit), commands run once:

1. `git apply --include='security/baseband-guard/*' features/001-bbg.patch` (SHA256 `b61d26be…a936da15`) → `baseband_guard.c` 270 lines, LF only, SHA256 `07f45991d2233522d24a3e2297fef89e64f99a2aa1c0249284b2e15f5c5ff53e`.
2. `git apply --check -v candidates/bbg-allow-cache-spinlock.patch` (SHA256 `ef50b027…5fb63eb193`) → **PASS** (exit 0).
3. `git apply` once → 293 lines, SHA256 `594c041d3ba40893df8cad0e8ab75b92bb30f0cd50842e7fbfe4ea1f9f452f15` (net +26/−3).

Locking review of the result:
- `allowed_devs` is only touched by `allow_has_locked()` (via `allow_has()` and `allow_add()`); no other iteration, and entries are never deleted.
- All callers are LSM hooks in process context (`file_permission` with `MAY_WRITE`, `inode_setattr`, `file_ioctl`/`file_ioctl_compat`), only after the `S_ISBLK` check. No lock nesting or recursion: `allow_add()` releases the lock from `allow_has()` before it takes the lock again.
- Nothing sleeps or logs under the lock: `kmalloc(GFP_ATOMIC)`, `kfree()` and `bb_pr()` all run outside it. The double check under the lock prevents duplicate insertion; the losing allocation is freed.
- The race being fixed is real: plain `hash_add()` racing with lock-free `hash_for_each_possible()` readers has no publication barrier.
- Optional, not required: `spin_lock()` would suffice (no IRQ-context users), or RCU readers (`hash_add_rcu`/`hash_for_each_possible_rcu`) would be lock-free because nothing is ever deleted. Neither is needed for correctness.
- Compile concerns: none found at source level (declarations before statements, `<linux/spinlock.h>` included, no unused symbols). Not compiled; that remains part of the full-build gate.

Status: candidate is correct at source level but still **not** in `features/kernel-replay.json`. Including it is a separate owner decision (proposed: add it as `003-bbg-allow-cache-spinlock.patch` after `001`/`002`, without editing the immutable feature patches).

## Checkpoint 2026-10-15 — resolved config and compilation preflight PASS (latest)

Record: `docs/validation/ksun-susfs-6.1-resolved-config.json`.

- The original workspace was missing, so it was reconstructed once in a disposable directory from the pinned commits. Core and feature replays reproduced every recorded identity exactly: trees `7e2b5164…`/`2fd43a2d…`, snapshots `3f08838c…`/`ce13bc5d…`, feature tree `b5db2f3c…`, staged diff `c06e6132…`.
- Neutron `06092026` archive SHA256 matches, 316 files, LLVM `f42c87ba`. Host packages were verified through a signed Ubuntu noble index and unpacked locally. **`pahole` v1.25 is now resolved.** `zstd` and `libzstd-dev` were added; the latter is a declared libelf-dev dependency that the earlier set lacked.
- `gki_defconfig` → `merge_config.sh -m` (locked fragment) → `olddefconfig`, fresh `O=`. Resolved `.config` SHA256 `41492e89ba04e6f93b14d2de89d653673195f05d7f3dac26a780ecd80665a92d`. Gate **PASS** after fixing a validator false positive: lowercase Kconfig symbols such as `CONFIG_FONT_8x16` were rejected. The fix was not a relaxation of any locked flag.
- `make prepare` **PASS**: resolve_btfids, modpost, sign-file, asm-offsets built; `.config` unchanged. resolve_btfids needs `HOSTCFLAGS="-idirafter <host-root>/usr/include"`.
- Not done: full compile/link/Image, BTF, KCFI, ABI/KMI, runtime. Guards remain false. No Actions, PR, release or flash.
- **Next:** one isolated full compile with exactly these identities. A local compile outside GitHub Actions is allowed; dispatching the kernel build workflow is owner-only. Decide first whether to include the BBG allow-cache candidate (proposed as `003`); including it changes the feature tree.

## Checkpoint 2026-10-15 — local Full LTO Image PASS (latest)

Record: `docs/validation/ksun-susfs-6.1-local-image.json`. Built in the session container, not GitHub Actions.

- `make Image` with exactly the resolved-config identities. Attempt 1: all 2805 objects compiled with 0 errors in 17 min, then `LD vmlinux.o` was killed by memory-cgroup OOM (ld.lld about 13.9 GB RSS, 14.3 GB limit). Attempt 2: a 14 GiB swapfile was added and the build resumed at the link only. **PASS** in 11 min; swap removed afterwards.
- `Image` SHA256 `d03696284c7425685da90e6a5147554cc9e62550ae846151d32b08d887b6d0ca`; `vmlinux` `4f0cd9eb…`; 0 undefined symbols; `susfs_init`, `ksu_lsm_hook_init`, `bbg_init`, `nomount_init` present; `.BTF`/`.BTF_ids` present; kCFI and Full LTO confirmed in the feature objects.
- BBG allow-cache candidate compiles with `W=1` and 0 warnings (object only; not part of this Image). Tree restored to `b5db2f3c`.
- **Next:** device boot/root/SUSFS test (owner); then wire the v2 candidate into `build.sh` behind the guard, the owner runs the workflow once, and then the dropdown label and guard are restored (W11). Full LTO link needs about 14 GB+ RAM: on a 14–16 GB host add swap.
- **2026-10-16:** device test **passed** on rothko (KernelSU Next v3.4.2 33365 built-in, root, SUSFS v2.3.0, SELinux enforcing). The dropdown label is now `KernelSU Next + SUSFS` and the ZIP has no `+Test` suffix; the guards (6.1.177, fullLTO, BBG on, non-Compat) and every frozen input stay unchanged.
- **2026-10-16 (owner-approved):** feature patch `004-bbrv3.patch` (byte-identical to the production BBRv3 patch) and the production networking extras were added to the candidate; feature tree `8109b744`. Local staging, config gate and `net/ipv4` compile pass (`ksun-susfs-6.1-bbrv3.json`); the Full LTO link and a device test are still needed.
- **2026-10-16 (owner-approved):** `005-bbr3-alias.patch` (byte-identical to `kernel-patches/bbrv3/bbr3-alias.patch`) also registers BBRv3 as `bbr3`; feature tree `978305ce`. A device test is needed.

## Checkpoint 2026-10-15 — feature 003 approved and built (latest)

- Owner approved the BBG allow-cache locking fix. It is now `features/003-bbg-allow-cache-spinlock.patch` (unchanged, SHA256 `ef50b027…`). It is listed in `features/kernel-replay.json` and as `reviewed_patches` in `configs/ksun-susfs-6.1-features.lock.json`, and the feature generator carries it.
- Strict replay of 001→002→003 on the clean frozen core gives feature tree `1246bd4c9a0afc0859ecbc4ad91031dab65aa413`, replacing `b5db2f3c`.
- Local Full LTO `Image` with 003: SHA256 `f5c687375f54ddbd64b36b33794ca433c429cd331b1941ebff8ac78c3b6fa148`; 0 undefined symbols; `allowed_devs_lock` present. Record: `ksun-susfs-6.1-local-image.json` → `image_with_feature_003`.
- The production build also applies 003 on top of pinned BBG `a54e0dc6`.
- Next: owner device test of this Image (boot, root, SUSFS, BBG), then wire the v2 candidate into `build.sh` and unlock the dropdown (W11).

## Checkpoint 2026-10-15 — candidate wired into the build workflow (latest)

- Dropdown option `KernelSU Next + SUSFS (uji)` builds exactly the validated candidate:
  - kernel `a7ba124a`, core replay, KSUN fork `2f858cb`;
  - frozen snapshots `3f08838c`/`ce13bc5d` (metadata now in `configs/ksun-susfs-6.1-features.lock.json` → `frozen_core`);
  - feature replay 001–003, which must give tree `1246bd4c`;
  - `gki_defconfig` + locked fragment + `olddefconfig`, then the resolved-config gate, then compile and an AnyKernel3 ZIP named `…+SuSFS+Test`.
- Production-only steps are skipped in this mode: BBRv3 networking, BBG/NoMount/KSUN `setup.sh` (provided by the feature patches) and `gki_defconfig.sh` fragments.
- Accepted only for 6.1.177 (lts), a fullLTO package, BBG enabled and no Compat variant; `build.sh` and `prepare` both reject anything else before any tool runs.
- The Neutron toolchain is now pinned for every build (`06092026`, SHA256 checked).
- Next: the owner runs the workflow once, then tests on a device (boot, root, SUSFS, BBG); then rename the option back to `KernelSU Next + SUSFS`.


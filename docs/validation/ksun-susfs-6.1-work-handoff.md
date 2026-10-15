# KSUN + SUSFS 6.1 — Work handoff checkpoint (2026-10-15)

**Status: V2 CORE SOURCE INTEGRATED; NOT READY FOR COMPILATION, RELEASE OR FLASH.**
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

## Exact continuation
1. Read `docs/validation/ksun-susfs-6.1-v2-integration.json` for actual tree/diff hashes, replay order, local logs and remaining gates. New lock: `configs/ksun-susfs-6.1-v2.lock.json`.
2. Current disposable workspace is `/workspace/scratch/d5d3c6fbcebc/candidate-v2`; kernel and KSUN subdirectories are intentionally patched/staged and recorded. If available, reuse them; do not replay patches or run historical preflight against them. If absent, reconstruct once using `scripts/prepare_ksun_susfs_candidate.py --locked-worktrees` and the exact clean pinned inputs; see the integration plan. The ordered manifests and four emitted patches are preserved in `kernel-patches/susfs/6.1-v2/replay/`.
3. Next unfinished work: inspect and pin NoMount for the requested bundle; lock compiler archive URL and verify downloaded bytes; generate and record a new resolved `.config`, commands and hashes. Core fragment `configs/ksun-susfs-6.1-v2.config` has Full LTO/CFI and NTSync disabled, but is not a final resolved config or final bundle. Shared `configs/features.config` still requests NTSync and must not be imported. BBG is outside the core replay.
4. Only after those preparation gates pass, consider one selective isolated compile/full Image attempt. Check offline version flags in its first compiler output. Stop on the first failure, preserve logs, diagnose before rerun. Full Image, final linking, manager compatibility, ABI/KMI and runtime are unverified for v2.

## Preserved evidence and rules
- Historical lock: `configs/ksun-susfs-6.1.lock.json`; partial build: `ksun-susfs-6.1-partial-build.json`; old evidence inventory: `ksun-susfs-6.1-replay-manifest.json`. None certifies the new v2 build.
- Original patch SHA256 `57e97f34055608a133594ff723ae5fa436b4559b1473d6e3284093c3ccb22156`; adjustment `6962a4a910ef74c776e7793cf64a064712fd26d71f90529208adbf35d9d88af1`; prepared patch `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b`.
- Historical main-patch-only pass: run `38691986084`, job `116279761088`. Reuse it; no redundant CI. The older evidence inventory is NOT accepted by replay.py; use the new schema-correct replay manifests.
- No NTSync, DroidSpaces or SUSFS LKM. No floating setup.sh, pull/stash/fuzz, automatic fallback or upstream update. No production guard removal.
- No duplicate work/downloads, speculative PRs, repeated successful Actions or checkpoint spam. Owner manually initiates builds/releases. NoMount + clean LTO remains the requested bundle direction. Update this checkpoint selectively.

Post-merge validation: ten archive-interface tests and five offline worktree tests passed. Only the affected five were rerun after correcting a helper-name merge error. The already successful complete core-source replay was not repeated.

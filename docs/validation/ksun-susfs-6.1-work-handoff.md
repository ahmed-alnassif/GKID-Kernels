# KSUN + SUSFS 6.1 — Work handoff checkpoint (2026-10-15)

**Status: INCOMPLETE / DO NOT BUILD, RELEASE, OR FLASH.** Resume with the user's command **Lanjutkan**. Repository `cogan17/Cogan`, branch `dev`. Focus only on built-in **KernelSU Next + kernel-patched SUSFS**. Production KSUN path and its KSUN+SUSFS guard must remain untouched.

## Confirmed and recorded
- Kernel source lock: `a7ba124af5a535078d3f83b3e145f9cc8ec651b8`; candidate KSUN: `pershoot/KernelSU-Next@2f858cb292265795dee2807759cec2eb8a7d79b1`.
- SUSFS historical source lock `a9bb4dd3ed248ada636b480bfdff70af704f1463` was unavailable in owner's fetched Git object set. Historical upstream revision `92aab7f579e9fb440a43e387c13bff519af13462` provides the four uploaded files. **Do not silently substitute commits.**
- Uploaded `susfs-verified.zip` four-file integrity: original GKI Android 14 / 6.1 patch, `susfs.h`, and `susfs_def.h` match recorded hashes. **`susfs.c` does not match old manifest SHA** `976f6d47a45260bcb0bb17d8ffe8beddeda398f8aba9bba54517ece9daf9e253`; uploaded file and owner's `git show` both yield `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7`. Candidate hash recorded separately; historical expected hash retained. Do not claim 4/4 match against old manifest.
- SUSFS patch SHA256 `57e97f34055608a133594ff723ae5fa436b4559b1473d6e3284093c3ccb22156`; KSUN adjustment patch SHA256 `6962a4a910ef74c776e7793cf64a064712fd26d71f90529208adbf35d9d88af1`; prepared patch SHA256 `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b`. Earlier isolated `git apply --check` passed (run `38691986084`, job `116279761088`), **not a full integrated candidate build**.
- KSUN pinned source inspection previously identified `ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr, size_t *count_ptr)`, `ksu_is_init_rc_hook_enabled`, and `susfs_init()` linkage. SUSFS source uses `ksu_cred` and `ksu_handle_setresuid`; API compatibility remains **unverified**.
- `scripts/ksun_susfs_replay.py` expects a separate `{kernel_commit, patches:[{path,sha256}]}` manifest; **do not feed it the evidence inventory JSON**.

## Next exact task for Work
1. Fetch pinned KSUN source files and examine definitions, linkage, conditional compilation, and signatures of `ksu_cred`, `ksu_handle_setresuid`, `ksu_handle_sys_read`, `susfs_init`; compare against the verified uploaded SUSFS source and prepared kernel patch. Record real API mismatches only; do not speculate.
2. Resolve `susfs.c` expected-vs-candidate SHA discrepancy with explicit source evidence and decide a controlled update; do not overwrite historical provenance silently.
3. Prepare clean **isolated** candidate integration and ordered SHA-locked patch replay; preserve production guard and original patch bytes. Avoid floating `setup.sh`, `git pull`, `stash`, fuzz, or automatic fallback.
4. Only after all source and patch preflights pass, consider one selective build; full Image and device runtime are **not verified**.

## Rules
- No redundant cloning/downloads, repeated CI, speculative PRs, or checkpoint spam. Maximize reuse of prior evidence; investigate first failure before any rerun.
- NTSync excluded; DroidSpaces disabled; NoMount + clean LTO preferred; owner manually triggers workflow/releases; no automatic upstream updates.
- Keep the source-only status explicit. Current evidence inventory: `docs/validation/ksun-susfs-6.1-replay-manifest.json`. Integration plan: `docs/validation/ksun-susfs-6.1-integration-plan.md` (contains stale claim of four matching manifest hashes; correct when editing that plan).
- Last checkpoint-related manifest commit: `9c2c4c255c5f58a96e4917a74ffd48022518fd87`.

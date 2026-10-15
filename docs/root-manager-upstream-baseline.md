# Root manager upstream baseline (GKID)

Status: documentation only; **not** a verified version/Manager compatibility matrix.

| Build identifier | Upstream source | Reference used in `build.sh` | Immutable commit | Manager compatibility |
| --- | --- | --- | --- | --- |
| KSUN | `KernelSU-Next/KernelSU-Next` | `v3.4.2` | `4c706b5938665866ebe16944a481a7b91e3396af` (upstream tag) | KSUN + SUSFS not verified |
| KSU | `tiann/KernelSU` | `main` | Recorded per build as `ROOT_MANAGER_SHA` (not pinned) | Not verified |
| BSU (BakaSU) | `Baka-SU/BakaSU` | `main` | Recorded per build as `ROOT_MANAGER_SHA` (not pinned) | Not verified |

## Evidence and limitations

- Source: `build.sh` in the `dev` branch, inspected 2026-10-15.
- KSUN `v3.4.2` tag resolves to upstream commit `4c706b5938665866ebe16944a481a7b91e3396af`; this is a source identity check, not a compiled or runtime compatibility result.
- KSUN `kernel/Kconfig` at this tag does not declare `CONFIG_KSU_SUSFS`. A dedicated, verified integration patch is necessary before enabling KSUN + SUSFS.
- Workflow input and matrix mapping for KSUN + SUSFS exist, but `build.sh` intentionally rejects the combination before installation. Do not dispatch this variant until a validated integration is implemented.
- The GKI 6.1 KSUN build in Actions run [38620320693](https://github.com/cogan17/Cogan/actions/runs/38620320693) compiled successfully; this does **not** establish a compatible Manager APK or runtime/boot success.
- The upstream branch names above are mutable. A branch name is not a reproducible version pin. The KSUN tag is more specific but must still be verified at checkout.
- KernelSU's SUSFS path includes additional local patch/setup handling; do not assume all KSU variants use the same source installation procedure.
- KSUN+SUSFS remains disabled pending compatibility validation.

## Follow-up checklist

- [x] Capture resolved upstream commit SHA and setup/install source for each selected manager in build metadata (`ROOT_MANAGER_REPO/REF/SHA` and `SUSFS_SHA` in `build-env-*.txt`, 2026-10-15).
- [ ] Capture relevant patchset commit SHAs and source versions.
- [ ] Verify matching Manager APK release/version and record the evidence.
- [ ] Decide and pin known-good revisions only after compatibility testing.
- [ ] Validate metadata generation offline before adding expensive build jobs.

Do not upgrade root manager revisions automatically, remove existing build choices, or infer device compatibility from a successful compile.

## Pin candidates — observed 2026-10-15, NOT applied

Read-only `git ls-remote` plus a blobless clone; nothing was built. All three upstream `kernel/setup.sh` installers print `Checkout default branch` and continue when the requested ref fails, so a pin is only meaningful with a post-install SHA check like the KSUN one (`build.sh`).

| Manager | `main` head | Latest tag (commit) | `main` ahead of tag | Assessment |
| --- | --- | --- | --- | --- |
| KernelSU (`tiann/KernelSU`) | `b94e0916bf6394cb75b03f50b0e8f5a90de3471c` (2026-10-15) | `v3.3.1` → `0c0fdb960178fa12d80d6cbcfdcb6ad8be6a865d` (2026-10-12) | 2 commits | Low drift. `v3.3.1` is a reasonable pin candidate **after** one KSU build on it succeeds. |
| BakaSU (`Baka-SU/BakaSU`) | `d7260ca1e5c128061122924d0d48754e361e135c` (2026-10-14) | `v4.2.0-rc3` → `239e1e8871b8fcd51a6e5b3002e0ba522fdd99fb` (2026-09-23); last stable `v4.1.0` → `0d27e685…` (2025-12-05) | 58 commits ahead of rc3; 1515 ahead of `v4.1.0` | Pinning to `v4.1.0` would be a large regression. An rc tag is not a stable baseline. Keep `main`, rely on the recorded SHA, and revisit at the next stable tag. |
| KSUN (`KernelSU-Next/KernelSU-Next`) | `dev` `723a599d9849aea29861d14370e42197bc40fe60` | `v3.4.2` → `4c706b5938665866ebe16944a481a7b91e3396af` | n/a | Already pinned and verified (PR #24). |

Manager APK: the KernelSU-family Kbuild derives `KSU_VERSION` from the checkout's commit count (`30000 + git rev-list --count HEAD` for KernelSU). Use the Manager APK from the **same upstream release/commit** as the recorded `ROOT_MANAGER_SHA`. A compatible APK version has not been verified on a device.

SUSFS: `GKI_SUSFS_COMMIT` entries in `functions.sh` remain commented out (branch tip). The commit actually used is now recorded as `SUSFS_SHA`; pin only after a build with that SHA is known good.

## KSUN v3.4.2 source inspection (2026-10-15)

- Upstream contains `kernel/susfs/` with `lsm_hook.c`, `ksu_umount_gate.c`, `imports_guard.c` and related files. These names alone do **not** establish integration with Simonpunk SUSFS.
- `kernel/Kconfig` does not declare `CONFIG_KSU_SUSFS`; `kernel/Kbuild` does not list those `kernel/susfs/` sources among `kernelsu-objs` in the inspected tag.
- Do not blindly apply `KernelSU/10_enable_susfs_for_ksu.patch` to KSUN: the patch targets a different manager source tree.
- Next: inspect KSUN's SUSFS integration points and compare against the selected Simonpunk patch revision before enabling compilation. Keep the existing fail-closed guard.

## Distinct SUSFS implementations (source inspection)

- KSUN v3.4.2 `kernel/susfs/Makefile` explicitly builds `susfs_guard_lkm.ko` via `obj-m`; it is an external loadable module, not a built-in `CONFIG_KSU_SUSFS` kernel option.
- KSUN `kernel/setup.sh` only wires `drivers/kernelsu` into the kernel tree; it does not itself build or load `susfs_guard_lkm.ko`.
- The LKM's `ksu_umount_gate.c` resolves `ksu_uid_should_umount` through kallsyms, with documented behavior when the symbol is missing and a potential stale pointer if KernelSU unloads first. This must be tested rather than assumed safe.
- **Decision:** Keep Cogan's current `KernelSU Next + SUSFS` build variant blocked. Do not silently substitute the LKM for Simonpunk's in-kernel patch. First choose an explicit supported implementation, pin its sources, validate patch/hook compatibility, and only then change build behavior.
- Upstream references: `KernelSU-Next/KernelSU-Next` tag `v3.4.2`, `kernel/susfs/Makefile`, `kernel/susfs/ksu_umount_gate.c`, and `kernel/setup.sh`.

## Active handoff — built-in candidate, 2026-10-15 (WIB)

**PARTIAL BUILD VERIFIED / FULL IMAGE AND RUNTIME HOLD:** the built-in KSUN driver, SUSFS core and namespace helper objects compile and pass a bounded relocatable link. Full Image, boot, matching Manager/root, SUSFS behavior and vendor ABI/KMI remain unverified.

The selected research candidate is the **pershoot built-in integration**, separate from the ordinary official KSUN `v3.4.2` baseline. It does not substitute `susfs_guard_lkm.ko` for Simonpunk's kernel hooks. Its immutable sources and payload hashes are saved in [`configs/ksun-susfs-6.1.lock.json`](../configs/ksun-susfs-6.1.lock.json). This is a source-pair lock, not a complete production build lock or permission to enable the variant.

| Candidate source | Immutable commit |
| --- | --- |
| GKI-Duchamp kernel 6.1.177 | `a7ba124af5a535078d3f83b3e145f9cc8ec651b8` |
| `pershoot/KernelSU-Next`, `dev-susfs` | `2f858cb292265795dee2807759cec2eb8a7d79b1` |
| `pershoot/susfs4ksu`, `gki-android14-6.1-dev` | `a9bb4dd3ed248ada636b480bfdff70af704f1463` |

Use the commit values, not moving branch tips. Keep normal KSUN on its existing official tag and immutable commit. The normal build now checks both the installed commit and tag against `4c706b5938665866ebe16944a481a7b91e3396af`; provenance resolves that tag, including annotated-tag peeling, rather than the retired `next` branch. Installed KSUN identity is included in build environment metadata after successful verification.

### Preserved source evidence

The earlier checkpoint `ksun_susfs_candidate_review.md` (snapshot 2026-10-15 05:07 WIB) records successful application to 24 kernel files, the corrected three-argument `ksu_handle_sys_read(fd, &buf, &count)`, full-source composition, and real built-in ARM64 Kconfig evaluation. These unchanged successful checks must not be repeated as new work.

The saved [`ksun-6.1-companion-adjustments.patch`](../kernel-patches/susfs/ksun-6.1-companion-adjustments.patch) reconstructs the already-validated delta. It changes the **SUSFS patch file**, not kernel C files directly:

1. Start with a clean SUSFS checkout at the locked commit and verify the `adaptation.input_sha256` value.
2. From that checkout, apply the saved delta once with `git apply /absolute/path/to/ksun-6.1-companion-adjustments.patch`.
3. Verify `adaptation.output_sha256`. The delta already includes Cogan's namespace-context correction; do not apply that correction a second time.
4. The resulting kernel patch and its matching `susfs.c`/headers belong to the locked kernel and KSUN candidate. Do not apply `KernelSU/10_enable_susfs_for_ksu.patch` to this KSUN source.

No new patch-application pass or kernel compilation is claimed by recovering these payloads. The delta and original companion/core/header byte hashes were matched to the preserved evidence.

### Build-result reconciliation and bundle gap

The earlier Image attempt stopped first at a host libelf include-path problem; the corrected second invocation resumed incrementally. At snapshot time, 23/24 tracked integration objects existed, but no final exit/link/Image result was recorded. The former workspace `/workspace/scratch/9e88f97f3592` is unavailable in this Work session, so its process, log and `build-result.json` could not be recovered. **The Image result remains unknown; do not claim that it passed or failed, or start another build merely because the session changed.**

That older source composition enabled DroidSpaces, omitted NoMount, and used ThinLTO with a portable Clang 18 toolchain. The current owner bundle fixes **NoMount + Clean LTO**, disables **DroidSpaces**, and defaults to **fullLTO**. Its additional source/config/link interaction and production toolchain have not been validated by the older result. A read-only inspection observed NoMount `master` at `7046c7ad3ee0bf4ae66e80f6b93b1e30db0cb4e3`; this observation is not a compatibility result or a change to the normal build's NoMount selection.

### Latest verified work — KSUN+SUSFS only

The owner's latest direction is **KSUN+SUSFS only**. NoMount object testing was stopped after preparation reported a missing host `bc`; it was not resumed. The existing repository feature defaults are context for the resolved configuration, not a separate development or runtime-validation claim.

- Full pinned source was composed with the saved SUSFS delta. The existing config script evaluated successfully with the repository's current fullLTO/CFI defaults. `.config` SHA-256: `5f47f9c03db802fadc24e396305bebd575f975f3ede9a181fe082e1cf2f7da67`.
- Neutron release `06092026`, Clang/LLD 24, LLVM `f42c87ba2c70219b1f4ad1f031a5b6a1ea6603fb` was verified against the release archive SHA-256. Compile commands confirm `-flto` and `-fsanitize=kcfi`.
- **36 built-in KSUN driver objects**, `fs/susfs.o` and `fs/namespace.o` compiled successfully. The verified `v3.4.2` base tag resolves to `4c706b5938665866ebe16944a481a7b91e3396af`; the candidate stays at `2f858cb292265795dee2807759cec2eb8a7d79b1`. Build output reports KSUN version `33365`, base tag `v3.4.2`, and SUSFS `v2.3.0`.
- A relocatable AArch64 link of the driver archive, SUSFS core and namespace object succeeded. It resolves 19 driver-to-core imports, three core-to-driver imports and the two namespace helper providers. No undefined symbol with the `ksu_` or `susfs_` prefix remains within this partial result.
- This is a **partial link**: 302 other kernel symbols remain external. It is not a `vmlinux`/Image link, BTF generation, device compatibility or runtime pass. No new full Image build, Actions kernel compilation, PR or flash was performed.

The exact scope, input identities, object/link hashes and diagnosed preparation errors are recorded in [`docs/validation/ksun-susfs-6.1-partial-build.json`](validation/ksun-susfs-6.1-partial-build.json). The source-pair lock remains `build_enabled: false`.

### Resume from here

1. Reuse `/workspace/scratch/a01fce1f8f50/candidate-stage/kernel`, `candidate-stage/out` and `candidate-stage/evidence` when available. The final scope-specific object log is `ksun-susfs-tag-and-namespace.log`; linkage proof is `ksun-susfs-namespace-linkage.json`. Do not repeat completed object, config or metadata checks.
2. The next unclosed gate is one justified full Image/link build for **KSUN+SUSFS**, using the pinned sources and verified Neutron release. This is a changed compiler/config composition from the unavailable older build, not a replay based only on a session change. Check BTF/host prerequisites and use existing successful objects. Diagnose the first failure before any rerun; no broad matrix or speculative retries.
3. Verify the resulting artifact, matching Manager/root, boot, SUSFS behavior, ordinary Wi-Fi and vendor ABI/KMI/runtime before readiness. A successful partial or full compile alone does not open the production guard.
4. Keep work confined to KSUN+SUSFS. Do not expand into NoMount/LTO feature development, other managers or TCP/BBR work. The older full Image result remains unknown unless its final log/artifact is recovered.

The workflow guard now stops in `prepare`, before cache/dependency jobs; direct invocations stop at script entry, before source downloads, installers or host changes. Regression checks cover both guards' lack of side effects and the dedicated dropdown mapping. Continue on this one `dev` branch; update this handoff instead of creating duplicate PRs or checkpoints.

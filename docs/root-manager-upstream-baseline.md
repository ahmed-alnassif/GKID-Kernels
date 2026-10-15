# Root manager upstream baseline (GKID)

Status: documentation only; **not** a verified version/Manager compatibility matrix.

| Build identifier | Upstream source | Reference used in `build.sh` | Immutable commit | Manager compatibility |
| --- | --- | --- | --- | --- |
| KSUN | `KernelSU-Next/KernelSU-Next` | `v3.4.2` | `4c706b5938665866ebe16944a481a7b91e3396af` (upstream tag) | KSUN + SUSFS not verified |
| KSU | `tiann/KernelSU` | `main` | Not recorded | Not verified |
| BSU (BakaSU) | `Baka-SU/BakaSU` | `main` | Not recorded | Not verified |

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

- [ ] Capture resolved upstream commit SHA and setup/install source for each selected manager in build metadata.
- [ ] Capture relevant patchset commit SHAs and source versions.
- [ ] Verify matching Manager APK release/version and record the evidence.
- [ ] Decide and pin known-good revisions only after compatibility testing.
- [ ] Validate metadata generation offline before adding expensive build jobs.

Do not upgrade root manager revisions automatically, remove existing build choices, or infer device compatibility from a successful compile.

## KSUN v3.4.2 source inspection (2026-10-15)

- Upstream contains `kernel/susfs/` with `lsm_hook.c`, `ksu_umount_gate.c`, `imports_guard.c` and related files. These names alone do **not** establish integration with Simonpunk SUSFS.
- `kernel/Kconfig` does not declare `CONFIG_KSU_SUSFS`; `kernel/Kbuild` does not list those `kernel/susfs/` sources among `kernelsu-objs` in the inspected tag.
- Do not blindly apply `KernelSU/10_enable_susfs_for_ksu.patch` to KSUN: the patch targets a different manager source tree.
- Next: inspect KSUN's SUSFS integration points and compare against the selected Simonpunk patch revision before enabling compilation. Keep the existing fail-closed guard.

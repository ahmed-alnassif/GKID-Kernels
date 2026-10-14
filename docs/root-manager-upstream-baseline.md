# Root manager upstream baseline (GKID)

Status: documentation only; **not** a verified version/Manager compatibility matrix.

| Build identifier | Upstream source | Reference used in `build.sh` | Immutable commit | Manager compatibility |
| --- | --- | --- | --- | --- |
| KSUN | `KernelSU-Next/KernelSU-Next` | `next` | Not recorded | Not verified |
| KSU | `tiann/KernelSU` | `main` | Not recorded | Not verified |
| BSU (BakaSU) | `Baka-SU/BakaSU` | `main` | Not recorded | Not verified |

## Evidence and limitations

- Source: `build.sh` in the `dev` branch, inspected 2026-10-15.
- The GKI 6.1 KSUN build in Actions run [38620320693](https://github.com/cogan17/Cogan/actions/runs/38620320693) compiled successfully; this does **not** establish a compatible Manager APK or runtime/boot success.
- The upstream branch names above are mutable. A branch name is not a reproducible version pin.
- KernelSU's SUSFS path includes additional local patch/setup handling; do not assume all KSU variants use the same source installation procedure.
- KSUN+SUSFS remains disabled pending compatibility validation.

## Follow-up checklist

- [ ] Capture resolved upstream commit SHA and setup/install source for each selected manager in build metadata.
- [ ] Capture relevant patchset commit SHAs and source versions.
- [ ] Verify matching Manager APK release/version and record the evidence.
- [ ] Decide and pin known-good revisions only after compatibility testing.
- [ ] Validate metadata generation offline before adding expensive build jobs.

Do not upgrade root manager revisions automatically, remove existing build choices, or infer device compatibility from a successful compile.

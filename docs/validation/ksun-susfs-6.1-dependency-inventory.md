# KSUN+SUSFS 6.1 dependency inventory (source audit)

Status: **SOURCE-ONLY / INCOMPLETE / NO BUILD**. Branch: `dev`. Evidence from `build.sh` and `functions.sh`.

| Dependency | Current acquisition | Risk | Required candidate evidence |
|---|---|---|---|
| NTSync base | `https://github.com/WildKernels/kernel_patches/raw/main/common/ntsync/ntsync_base.patch` | floating main | exact upstream commit, downloaded SHA256, ordered local patch |
| NTSync Android14 6.1 compat | `https://github.com/WildKernels/kernel_patches/raw/main/common/ntsync/ntsync_compat_android14-6.1.patch` | floating main | exact commit, SHA256, ordering |
| Baseband Guard | `https://github.com/vc-teahouse/Baseband-guard/raw/main/setup.sh` piped into bash | floating executable script | pinned source revision, reviewed script and its transitive downloads, resulting diff and hashes |
| NoMount | `https://raw.githubusercontent.com/maxsteeel/nomount/refs/heads/dev/kernel/setup.sh` then `bash ... master` | floating dev installer and possible floating master content | pin installer and transitive content; verify source revision and resulting diff |
| Antman toolchain installer | `https://raw.githubusercontent.com/Neutron-Toolchains/antman/main/antman` | floating executable installer | pinned installer and compiler archive bytes, version and SHA256 |

## Verification rules
1. Do not equate an upstream commit reference with the exact bytes used by the current workflow.
2. Inspect installers for secondary network calls and moving refs before pinning.
3. Capture hashes and exact order of modifications from an isolated checkout. Do not reuse an unverified historical working tree.
4. Preserve the production KSUN v3.4.2 path and the KSUN+SUSFS build guard.
5. Do not run new CI, publish artifacts, or flash based on this inventory.

## Next gate
Prepare local immutable inputs for the candidate, beginning with NTSync base + Android14 6.1 compat. Validate all hashes before applying. Then investigate Baseband Guard, NoMount and toolchain transitive inputs. This document does not claim these inputs have been locked.

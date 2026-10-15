# KSUN+SUSFS 6.1 dependency inventory (source audit)

Status: **SOURCE-ONLY / INCOMPLETE / NO BUILD**. NTSync is excluded by owner decision; the historical NTSync provenance pointer is not a replay input. Branch: `dev`. Evidence from `build.sh` and `functions.sh`.

| Dependency | Current acquisition | Risk | Required candidate evidence |
|---|---|---|---|
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
The minimal KSUN+SUSFS v2 source bundle is prepared; see `ksun-susfs-6.1-api-review.md`. Next lock Baseband Guard, NoMount and toolchain transitive inputs before a full feature candidate or compilation. NTSync must not be restored; DroidSpaces remains disabled. This document does not claim these remaining inputs have been locked.

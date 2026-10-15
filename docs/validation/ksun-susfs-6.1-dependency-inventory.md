# KSUN+SUSFS 6.1 dependency inventory (source audit)

Status: **SOURCE-ONLY / INCOMPLETE / NO BUILD**. Branch: `dev`. Acquisition audit of shared production scripts; the isolated v2 route does not execute these installers. See `ksun-susfs-6.1-v2-integration.json` for completed core-source integration.

| Dependency | Current acquisition | Risk | Required candidate evidence |
|---|---|---|---|
| NTSync | Excluded by owner decision; historical prerequisite references retained only as evidence | Shared `configs/features.config` still requests it | Never import that shared fragment into v2; its dedicated core fragment explicitly disables NTSync |
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
Core KSUN + kernel-patched SUSFS source integration is complete for the distinct v2 candidate. Next investigate pinned NoMount inputs for the requested bundle and the compiler archive, then generate and record the resolved configuration. NTSync and DroidSpaces remain excluded. Baseband Guard remains outside the core v2 replay; no floating installer is executed. This document does not claim these additional inputs have been locked.

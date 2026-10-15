# KSUN + SUSFS 6.1 — BBG / NoMount Makefile source audit

Scope: source-only review of pinned feature patches on branch `dev`. This is **not** compile, link, runtime or production approval.

## Confirmed source observations

- `kernel-patches/susfs/6.1-v2/features/001-bbg.patch` adds `security/baseband-guard/Makefile` with conditional `$(shell ...)` invocations of `$(HOSTCC)`, `genheaders`, `mkdir`, and `mv` to populate `$(objtree)/security/selinux/{flask.h,av_permissions.h}` when `flask.h` is absent. Shell-command failures are not checked explicitly. Assess interaction with the kernel's existing SELinux header-generation rules, especially parallel builds and out-of-tree output.
- The same BBG Makefile uses `$(error ...)` if `CONFIG_BBG=y`, a modern `DEFINE_LSM` is detected, and `CONFIG_LSM` does not contain `baseband_guard`. The candidate fragment requests the token; only the resolved final `.config` can confirm acceptance.
- `kernel-patches/susfs/6.1-v2/features/002-nomount.patch` adds `fs/nomount/Makefile` with `ccflags-y += -std=gnu11 -Wno-declaration-after-statement -O3 -fno-stack-protector`. Check the necessity and interaction of these flags with the selected kernel hardening, Clang Full LTO and CFI. Do not assume a build failure without evidence.
- `CONFIG_NOMOUNT` is declared `tristate`; the locked candidate explicitly requests `y`. Confirm the resolved built-in value rather than allowing `m`.

## Targeted preflight before an isolated compile

1. Recover the exact frozen source trees and pinned Neutron compiler without replaying patches on an already staged feature tree.
2. Prepare host tools, including the pinned `pahole`, without unverified substitution.
3. Generate fresh `gki_defconfig`, merge only `configs/ksun-susfs-6.1-features.config`, then run `olddefconfig`. Record exact environment and SHA256.
4. Confirm `CONFIG_BBG=y`, `CONFIG_NOMOUNT=y`, `CONFIG_KSU=y`, `CONFIG_KSU_SUSFS=y`, `CONFIG_KEYS=y`, `CONFIG_LTO_CLANG_FULL=y`, `CONFIG_CFI_CLANG=y`, and the `baseband_guard` LSM token. Confirm NTSync, DroidSpaces and SUSFS LKM remain excluded.
5. Inspect BBG's SELinux header-generation prerequisites and NoMount compiler flags in that resolved environment. Make any adaptation in a new isolated candidate patch with a new checksum and lock; never silently modify the pinned patches.
6. Only after these checks pass report readiness for isolated compilation. Do not enable production guards, dispatch Actions, release or flash.

No source patch, lock, CI, or production guard was modified by this audit.

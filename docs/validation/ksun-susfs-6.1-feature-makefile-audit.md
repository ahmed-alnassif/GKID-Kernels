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

## Offline resolved-config validator unit-test result

On 2026-10-15, the GitHub connector supplied the source of `scripts/check_ksun_susfs_resolved_config.py` and `tests/test_ksun_susfs_resolved_config.py` from branch `dev`. Their content was reproduced in a temporary local test directory (the full repository could not be cloned because DNS resolution for github.com failed), then executed with `python3 -m unittest discover -s tests -p 'test_ksun_susfs_resolved_config.py' -v`.

Result: **10 tests run, 10 passed, 0 failures, 0 errors** (0.021 s). This is a copied-source offline unit test, not a verified checkout-based CI run. It does not establish that a kernel `.config` has been generated or resolved, that the full toolchain is ready, or that kernel compilation succeeds.

Next gate: restore the pinned integrated kernel tree, generate fresh `gki_defconfig` plus locked fragment via `olddefconfig`, and run the read-only validator on the resulting `.config`. Preserve the existing production, Actions, release, and flash restrictions.

## NoMount compiler-flag decision gate (source-only follow-up)

The pinned `002-nomount.patch` declares `CONFIG_NOMOUNT` as `tristate` with `default y`, and its Makefile adds `-std=gnu11 -Wno-declaration-after-statement -O3 -fno-stack-protector` to `ccflags-y`. The locked fragment and validator require `CONFIG_NOMOUNT=y`; `m` is not an acceptable substitute. `-fno-stack-protector` explicitly disables stack-protector instrumentation for these compilation units, and `-O3` overrides the ordinary optimization choice for this directory. Neither flag alone proves a build failure or a CFI bypass.

**Gate:** before isolated compilation, inspect the *effective* compiler command for `fs/nomount/nomount.o` using the pinned Neutron toolchain, and determine whether the local `-fno-stack-protector` is required or conflicts with the project's hardening policy. Confirm Full LTO/CFI are still present in the resolved `.config`. If adaptation is justified, prepare a new separately checksummed candidate patch and update its lock only after review; do **not** silently alter the existing pinned patch or enable builds. This is a pending source/toolchain-dependent check, not a completed compiler test.

## BBG LSM API compatibility decision gate (source-only follow-up)

The locked BBG patch uses a Makefile text probe for the exact macro `#define DEFINE_LSM(lsm)` in `include/linux/lsm_hooks.h`, while its source conditionally registers with `DEFINE_LSM(baseband_guard)` or `security_initcall(bbg_init)`. Its `security_add_hooks_compat()` chooses the **three-argument** `security_add_hooks(hooks, count, "baseband_guard")` for kernel versions from 4.11 through 6.7, and the `struct lsm_id *` variant from 6.8 onward. Vendor backports can invalidate both version-only assumptions and the exact-text macro probe.

**Required before compile readiness:** inspect the pinned integrated kernel's actual `include/linux/lsm_hooks.h`, `include/linux/lsm_hook_defs.h`, and `security/security.c` declarations/definitions. Verify whether `DEFINE_LSM` exists and whether the three-argument `security_add_hooks` signature matches the selected branch; ensure only one BBG initialization/registration path is active. Also inspect the compatibility probes for `file_ioctl_compat`, `selinux_state`, and block-device partition APIs against real declarations, not grep matches alone. Do not treat source-only inspection as a successful compiler test. Keep the pinned patch untouched unless an isolated, reviewed adaptation is required.

## BBG allowed-device cache concurrency gate (source-only)

The pinned BBG patch declares a global `DEFINE_HASHTABLE(allowed_devs, 7)`. `allow_has()` traverses it with `hash_for_each_possible()`, while `allow_add()` calls `allow_has()`, allocates with `GFP_ATOMIC`, and inserts via `hash_add()`. No lock or RCU read-side protection is present around those accesses. Concurrent LSM hook invocations could race with insertion, including duplicate entries. This is a **source-level concurrency hazard**, not a demonstrated runtime failure.

**Decision gate:** before production readiness, prepare and review a separate candidate change that serializes lookups and insertions using a kernel-appropriate non-sleeping synchronization scheme. Do not hold a spinlock across allocation, block-device lookups, logging, or other potentially sleeping work; handle duplicate insertion after reacquiring the lock. Verify that the lookup and insertion paths share the same protection, and test under concurrency with the pinned integrated kernel. Keep the current checksummed BBG patch, production guards, and build/release restrictions unchanged until a reviewed adaptation is ready.

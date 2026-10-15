# KSUN + SUSFS 6.1 — candidate v2 API review

Reviewed 2026-10-15. **Source-level API review passed for the exact bytes below.**
Compilation, final linking, manager APK compatibility, ABI/KMI and device runtime
remain unverified for this new candidate. Production stays disabled.

## Source identity and controlled selection

Kernel: `ahmed-alnassif/GKI-Duchamp-6.1@a7ba124af5a535078d3f83b3e145f9cc8ec651b8`.
KSUN: `pershoot/KernelSU-Next@2f858cb292265795dee2807759cec2eb8a7d79b1`.
Both were independently checked out at those exact commits. The four files in
`kernel-patches/susfs/6.1-v2/source/` preserve the uploaded `susfs-verified.zip`
bytes. They are separately locked in `configs/ksun-susfs-6.1-v2.lock.json`.

The owner supplied upstream `git show` evidence for Simonpunk commit
`92aab7f579e9fb440a43e387c13bff519af13462`; that commit was **not independently
retrieved this session**. Content selection is therefore anchored in the uploaded
file bytes, with the owner-reported upstream provenance explicitly distinguished.

| File | Candidate SHA256 | Historical manifest comparison |
| --- | --- | --- |
| Original kernel patch | `57e97f34055608a133594ff723ae5fa436b4559b1473d6e3284093c3ccb22156` | Match |
| `susfs.h` | `fafff787b8856bd37a6736c2f0bbc5a57fd1f36232be267936f892fb57bc5120` | Match |
| `susfs_def.h` | `db7f98dcf8119a4eb5c45c05205b6c1065766047d6f803b0e86f3d14b1a251f0` | Match |
| `susfs.c` | `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7` | Different; old expected hash `976f6d47a45260bcb0bb17d8ffe8beddeda398f8aba9bba54517ece9daf9e253` retained |

This explicitly selects a **new source-only candidate v2**, after reviewing its
APIs. It does not repair or replace the historical source lock
`a9bb4dd3ed248ada636b480bfdff70af704f1463`, recover that historical file, or transfer
the historical partial-build/config/object results to v2. The cause and exact
content delta behind the old `susfs.c` checksum remain unknown.

## Definitions, consumers and conditional compilation

All KSUN paths in this table are relative to its pinned repository. SUSFS paths
refer to the locked v2 companion files or the prepared main kernel patch.

| API | Definition and consumer | Finding |
| --- | --- | --- |
| `struct cred *ksu_cred` | Global definition `kernel/core/init.c:89`; `susfs.c:30,142,1522` | External linkage and pointer type match. Assigned by `prepare_creds()` at init.c:161; deferred SUSFS work checks for NULL. |
| `int ksu_handle_setresuid(uid_t, uid_t, uid_t)` | `kernel/hook/setuid_hook.c:164` and header; prepared `kernel/sys.c` insertion | Three-argument definition is selected by `CONFIG_KSU_SUSFS`. The two-argument definition at :181 is the `#else` branch and must not be used for this variant. `Kbuild` always includes `hook/setuid_hook.o`. |
| `void ksu_handle_sys_read(unsigned int, char __user **, size_t *)` | `kernel/runtime/ksud_integration.c:533` and `kernel/runtime/ksud.h:11`; prepared `fs/read_write.c` | The raw upstream patch has a one-argument declaration/call. The existing locked companion adjustment corrects both to three arguments and passes `&buf, &count`. No additional shim is needed. |
| `ksu_is_init_rc_hook_enabled` | `DEFINE_STATIC_KEY_TRUE` at `kernel/runtime/ksud_integration.c:36`; prepared read/stat hooks | `struct static_key_true` declaration matches; provider is under `CONFIG_KSU_SUSFS`. `runtime/ksud_integration.o` is always listed in built-in KSUN `Kbuild`. |
| `void susfs_init(void)` | `susfs.h:241`, `susfs.c:1530`; KSUN `kernel/core/init.c:118` | Declaration/definition/call match. Called under `CONFIG_KSU_SUSFS`. `fs/Makefile` builds `susfs.o` under the same symbol. The init body only initializes work and logs; it does not dereference `ksu_cred` before assignment. |
| `void setup_selinux(const char *, struct cred *)` | `kernel/selinux/selinux.c:138`, header; `susfs.c:29,1480` | Signature and external linkage match; `selinux/selinux.o` is included in built-in KSUN. |
| `bool susfs_is_current_ksu_domain(void)` | `kernel/selinux/selinux.c:398`, header; `susfs.c:28` and VFS patch | Signature matches; definition under `CONFIG_KSU_SUSFS`, built-in provider selected. |
| Statfs wrappers | Prepared `fs/statfs.c` defines `int calculate_f_flags_wrapper(struct vfsmount *)` and `int statfs_by_dentry_wrapper(struct dentry *, struct kstatfs *)`; `susfs.c:277–278` imports them | Matching types and global linkage under the selected kstat feature; retained from concurrent source review. |
| Namespace helpers | Prepared `fs/namespace.c` defines `susfs_get_non_sus_mnt_id_from_mnt(struct mount *)` and `susfs_get_non_sus_vfsmnt_from_vfsmnt(struct vfsmount *)`; `susfs.c:31–32` | Return types `int` and `struct vfsmount *` match; both sides use `CONFIG_KSU_SUSFS_SUS_MOUNT`. |

The other main-patch KSUN imports were inspected against their built-in providers:

| Imports | Built-in provider | Signature/config result |
| --- | --- | --- |
| `ksu_is_input_hook_enabled`, `ksu_handle_input_handle_event` | `runtime/ksud_integration.c:37,568` | Static key true and `int(unsigned int *, unsigned int *, int *)` match. |
| `ksu_su_compat_enabled`, `ksu_handle_execveat`, `ksu_handle_execveat_sucompat`, `ksu_handle_post_execveat_sucompat` | `feature/sucompat.c:53,289,226,277` | Five-argument exec hooks and six-argument post-hook match. SUSFS branches select the kernel `struct filename **` / `void *` interfaces. |
| `ksu_handle_faccessat`, `ksu_handle_stat` | `feature/sucompat.c:318,365` | `int(int *, struct filename **, int *, int *)` and `int(int *, struct filename **, int *)` match the SUSFS branches. |
| `__ksu_is_allow_uid_for_current` | `policy/allowlist.c:297` | `bool(uid_t)` matches. |
| `ksu_handle_vfs_fstat` | `runtime/ksud_integration.c:544` | `void(int, loff_t *)` matches under SUSFS. |
| `ksu_handle_sys_reboot` | `supercall/dispatch.c:1068` | `int(int, int, unsigned int, void __user **)` matches under SUSFS. |
| `susfs_ksu_sid`, `susfs_priv_app_sid` | `selinux/selinux.c:99,103` | Global `u32` under SUSFS; matching external declarations. |
| `fake_state`, `fake_status`, `fake_status_initialize_key`, `ksu_selinux_hide_running`, `ksu_selinux_hide_enabled`, `initialize_fake_status` | `feature/selinux_hide.c:41–46,327–330` | Global state, page pointer, static key false, booleans and zero-argument function match. `fake_state` is present for kernel <6.6, including target 6.1. |

All 14 distinct SUSFS command handlers called by the SUSFS reboot dispatcher
exist in both `susfs.h` and `susfs.c`: path, path-loop, kstat add/update, map,
open-redirect, uname, logging, cmdline/bootconfig, mount hiding, AVC logging,
enabled-features, variant and version. Their `void(void __user **)` interfaces
match the dispatcher argument. Work scheduling uses the shared global
`struct work_struct susfs_extra_works` defined in `susfs.c:1520`.

The reviewed source files are SHA256-locked. Preparation verifies those bytes and
clean exact Git HEADs before mutation; it does not pretend to be a general C type
checker or a link test. No API mismatch remains in the inspected interfaces after
the existing read-hook adjustment. Other compiler/kernel compatibility failures
can still be found by the later compile/link gate.

## Built-in wiring and offline metadata

`kernel/Kbuild` selects every provider above. It does not include the separate
`kernel/susfs/` LKM implementation in `kernelsu-objs`. KSUN init blacklists
`susfs_guard_lkm`; the isolated route never builds or loads it. No generic
`10_enable_susfs_for_ksu.patch` is applied to the already SUSFS-aware KSUN fork.

The upstream version-discovery block can fetch history implicitly. For v2 only,
the preparation script emits a reviewable KSUN patch replacing that block with
offline constants `KSU_VERSION=33365`, `KSU_VERSION_TAG=v3.4.2`. Complete local
history independently returned 3365 reachable commits, and the local nearest tag
`v3.4.2` resolves to `4c706b5938665866ebe16944a481a7b91e3396af`. The script checks
these facts again before creating the candidate. The input checkout and
production KSUN path remain untouched.

The concurrent review at `7dcdef0` also records `kernel/extras.c` importing the
static-false `susfs_is_avc_log_spoofing_enabled` key supplied by `susfs.c`. Its
pinned blob identity remains in the preserved archive lock. ARM64, KPROBES and
THREAD_INFO_IN_TASK are explicit requirements in the proposed core configuration
fragment. The original ZIP preparation interface and its tests are preserved;
the completed isolated source stage uses the added **--locked-worktrees** mode.

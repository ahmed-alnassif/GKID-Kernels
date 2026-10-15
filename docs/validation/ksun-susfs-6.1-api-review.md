# KSUN + SUSFS 6.1 — v2 source contracts and isolated staging

Review date: 2026-10-15. Repository: `cogan17/Cogan`, branch `dev`, base `c140b2053cc035ad8ad9b5b1a4a5f56402cc87a3`.

**Selected source contracts: PASS. Compilation readiness: BLOCKED.** This is source inspection and preparation of a new candidate. It does not reproduce the historical partial build or verify full linking, KCFI, an Image, ABI/KMI, manager compatibility, or device runtime. No Actions or PR was started for this work.

## Immutable inputs and source decision

- Kernel: `ahmed-alnassif/GKI-Duchamp-6.1@a7ba124af5a535078d3f83b3e145f9cc8ec651b8`.
- Built-in KSUN: `pershoot/KernelSU-Next@2f858cb292265795dee2807759cec2eb8a7d79b1`. Inspected file bytes were checked against the pinned Git blob identities. The reviewed provider blobs are recorded in `configs/ksun-susfs-6.1-candidate-v2.json`.
- SUSFS: owner-uploaded `susfs-verified.zip`, SHA256 `4308a05c09462c22edf390be066c5e31503de8585891fd2829533c71cbed0777`. Attribution to `simonpunk/susfs4ksu@92aab7f579e9fb440a43e387c13bff519af13462` comes from the owner Git evidence retained in the previous handoff. This review independently verified the uploaded bytes; it did not obtain a fresh GitLab checkout.
- Historical `pershoot/susfs4ksu@a9bb4dd3ed248ada636b480bfdff70af704f1463` and historical `susfs.c` SHA256 `976f6d47a45260bcb0bb17d8ffe8beddeda398f8aba9bba54517ece9daf9e253` remain unchanged in the historical lock and evidence inventory. Their original byte provenance remains unresolved.
- Controlled decision: create **source candidate v2**, using uploaded `susfs.c` SHA256 `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7`. This is an explicit, separately locked source selection following the contracts below. It is not a claim that the historical commit or tested working tree was recovered.
- Against the historical manifest, **three of four** uploaded files match. Against the new v2 per-file lock, all four uploaded files match. Archive recompression is immaterial to staging; per-file checksums are authoritative.

## Selected API contracts

Paths and line numbers in this table refer to the immutable KSUN source above, the verified uploaded companion files, or the prepared kernel patch with SHA256 `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b`.

| Contract | Consumer and provider evidence | Result and configuration boundary |
| --- | --- | --- |
| `struct cred *ksu_cred` | `susfs.c:30` declares the external pointer; KSUN `kernel/core/init.c:89` defines it globally and `:161` initializes it with `prepare_creds()` | Matching type and built-in linkage. SUSFS initialization only initializes work; its work callback checks the pointer before using it. Initialization/runtime behavior is not tested. |
| `int ksu_handle_setresuid(uid_t, uid_t, uid_t)` | Prepared patch adds declaration and call in `kernel/sys.c`; KSUN `kernel/hook/setuid_hook.c:164` and its header provide the three-argument form | Match **under `CONFIG_KSU_SUSFS=y`**. The two-argument definition at `:181` is the alternative non-SUSFS branch. `susfs.c` mentions this hook in a comment; the actual caller is the patched kernel, not `susfs.c`. |
| `void ksu_handle_sys_read(unsigned int, char __user **, size_t *)` | Prepared patch `:1620` declares the three-argument form and `:1627` passes `fd, &buf, &count`; KSUN `kernel/runtime/ksud_integration.c:533` defines it | Match after the already locked companion adjustment. The original one-argument patch must not be replayed directly. |
| `ksu_is_init_rc_hook_enabled` | Prepared read/fstat hooks declare `struct static_key_true`; KSUN `kernel/runtime/ksud_integration.c:36` uses `DEFINE_STATIC_KEY_TRUE` | Matching global static-key type under `CONFIG_KSU_SUSFS`. |
| `void susfs_init(void)` | Uploaded `susfs.h:241` declares it; `susfs.c:1530` defines it; KSUN `kernel/core/init.c:118` invokes it | Matching built-in provider. The prepared `fs/Makefile` addition selects `susfs.o` with `CONFIG_KSU_SUSFS`. |
| `susfs_extra_works` and zygote SIDs | Uploaded `susfs.c:1520` defines `struct work_struct`; KSUN setuid/dispatch sources import it. KSUN `kernel/selinux/selinux.c:101-102` defines both zygote SIDs | Global types and selected SUSFS branches agree. This checks presence and source shape, not scheduling safety under runtime load. |
| SELinux helpers imported by SUSFS | Uploaded `susfs.c:28-30` imports `susfs_is_current_ksu_domain(void)` and `setup_selinux(const char *, struct cred *)`; KSUN `kernel/selinux/selinux.c:398` and `:138` define them | Return and parameter types match. No module export is needed for the selected built-in layout. |
| exec, access, stat, input and reboot hooks | Prepared patch declarations match KSUN `kernel/feature/sucompat.c` SUSFS definitions, `kernel/policy/allowlist.c:297`, `kernel/runtime/ksud_integration.c:568`, and `kernel/supercall/dispatch.c:1068` | Source shapes agree: exec `int *, struct filename **, void *, void *, int *`; post-exec adds `int *`; access/stat use `struct filename **`; input uses three integer pointers; reboot uses `void __user **`. |
| SUSFS command dispatcher | KSUN `kernel/supercall/dispatch.c` includes uploaded `<linux/susfs.h>` under `CONFIG_KSU_SUSFS` and calls its declared command functions | Reviewed command functions are present in uploaded `susfs.c`; feature switches agree with KSUN Kconfig and `configs/susfs.config`. This is not a manager APK protocol/runtime test. |
| Namespace and statfs helpers imported by SUSFS | Uploaded `susfs.c` imports `susfs_get_non_sus_mnt_id_from_mnt`, `susfs_get_non_sus_vfsmnt_from_vfsmnt`, `calculate_f_flags_wrapper`, and `statfs_by_dentry_wrapper` | Matching global providers are added by the prepared patch to `fs/namespace.c` and `fs/statfs.c`; no guessed shim or LKM fallback is added. |
| SELinux-hide globals and AVC key | Prepared SELinux changes import fake state/status/initialization globals from KSUN `kernel/feature/selinux_hide.c`; KSUN `kernel/extras.c` imports the static false AVC key defined in uploaded `susfs.c:1195` | Inspected providers have external linkage and matching source types. Whole-kernel SELinux build/link remains pending. |

`kernel/Kbuild` includes `core/init.o`, `hook/setuid_hook.o`, `runtime/ksud_integration.o`, `selinux/selinux.o`, and the other reviewed built-in providers. It does not add the separate `kernel/susfs/` LKM implementation to this source list. Require `CONFIG_KSU=y`, `CONFIG_KSU_SUSFS=y`, `CONFIG_THREAD_INFO_IN_TASK=y`, and the recorded ARM64/KPROBES configuration before any compilation. A selected-source contract pass is not a full C type-check or exhaustive compiler proof.

## Reproducible isolated preparation

New driver patch: `kernel-patches/susfs/ksun-6.1-driver-integration.patch`, SHA256 `01f05f137353ad14823da02f9aeaedf981b83a7f07e2b2327b6d379af4362149`. It adds the explicit driver Makefile/Kconfig entries and symlink `drivers/kernelsu -> ../../ksun/kernel`. It was strictly checked and applied once to a **two-file fixture** containing the pinned kernel `drivers/Makefile` and `drivers/Kconfig` blobs recorded in the candidate lock. This fixture is not a complete kernel checkout.

From Cogan root, prepare a bundle from the existing owner archive:

```sh
python3 scripts/prepare_ksun_susfs_candidate.py /absolute/path/to/susfs-verified.zip /absolute/path/to/new-bundle
```

This command was executed successfully on the real uploaded archive. It verifies all four members and the driver patch, invokes the existing checksum-locked patch preparer, and creates `kernel-replay.json`, two ordered patches, companion sources, and a copy of the v2 lock. The historical evidence inventory JSON is not used as an executable replay manifest. Original uploaded and production patch bytes are preserved.

When complete pinned checkouts are available, use an independent directory containing sibling `kernel` and `ksun` checkouts, and a new output directory outside both:

```sh
python3 scripts/prepare_ksun_susfs_candidate.py /absolute/path/to/susfs-verified.zip /isolated/new-bundle --kernel /isolated/kernel --ksun /isolated/ksun
```

The optional staging mode verifies checkout roots, exact HEADs, clean status, absent destinations, and a nonshallow KSUN checkout before source mutation. KSUN Kbuild attempts `git fetch --unshallow` for a shallow repository, so that input is rejected. The existing replay helper preflights the entire series in a disposable index, then strictly applies the driver patch followed by the prepared SUSFS patch. Companion files are copied exclusively and rehashed. Stage evidence records tracked diff digest, untracked status, and companion digests. A failed staging operation preserves its diagnostics/tree for investigation; do not blindly retry or reset it.

**The optional staging mode has passed synthetic offline tests; it has not run against complete real kernel/KSUN checkouts in this session.** The historical workspace `/workspace/scratch/a01fce1f8f50` does not exist. No clean full source tree, generated objects or resolved configuration was recovered.

## Local validation and next gate

- Ten new offline tests passed: bundle-only behavior, successful synthetic full stage, wrong companion/driver bytes, ZIP path/link rejection, wrong HEAD/dirty sources, occupied destinations/output, shallow KSUN rejection, and a later-patch failure leaving the kernel clean without copying companions.
- Existing root matrix/early guard assertions passed; repository Python syntax validation passed.
- The previously green Actions main-patch apply check was reused and not rerun. New driver-entry fixture validation is a separate, narrowly scoped check.
- `build.sh`, production workflows, the existing replay/preparer helpers and historical lock/partial-build record remain byte-identical to the starting revision. No full compilation, release or flash was performed.

Before compilation: stage complete clean pinned sources; lock the intended BBG/NoMount feature replay with NTSync excluded and DroidSpaces disabled; resolve KSUN version metadata against the immutable v3.4.2 base; obtain the exact toolchain URL/bytes/checksum; and record exact config generation commands plus the resolved config and clean-LTO choice. Only after these gates pass should one selective compile/link/Image attempt be considered. Production KSUN+SUSFS remains disabled.

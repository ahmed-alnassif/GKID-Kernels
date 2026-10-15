# KSUN + SUSFS 6.1 — Resume gate (manual, fail closed)

Scope: **KSUN + SUSFS only**. This document does not authorize a production workflow, release, flash, or removal of the existing KSUN+SUSFS guard.

## Provenance

Use `docs/validation/ksun-susfs-6.1-partial-build.json` as the single source of truth for the exact kernel, KSUN, SUSFS, resolved configuration, object hashes, and toolchain. The prior candidate workspace was recorded as `/workspace/scratch/a01fce1f8f50`; **that path is historical, not proof that the workspace still exists**.

Do not substitute the normal KSUN `v3.4.2` checkout for the pinned candidate commit: the tested candidate had a different HEAD. Do not reapply SUSFS patches to an already-patched tree or infer that matching Git HEAD alone proves an identical working tree.

## Gate A — Recover existing candidate (preferred)

1. Locate the **actual** candidate kernel checkout, KSUN checkout, SUSFS checkout, and output directory containing the prior `.config`, `drivers/kernelsu/built-in.a`, `fs/susfs.o`, and `fs/namespace.o`. Do not recreate empty directories to satisfy a path.
2. Preserve the original evidence and logs. Record `git status --porcelain` for all three source trees, plus the compiler identity. Inspect any working-tree changes against the prior evidence; the preflight checks HEAD, not uncommitted patch content.
3. From the **Cogan repository root**, run (replace placeholders with real paths):

   ```sh
   python3 -m unittest discover -s tests -p 'test_ksun_susfs_preflight.py'
   python3 scripts/ksun_susfs_preflight.py \
     /absolute/path/to/kernel \
     /absolute/path/to/out \
     /absolute/path/to/ksun \
     /absolute/path/to/susfs
   ```

4. A failed preflight is a **stop**, not a reason to rerun old successful compilation steps. Investigate the first mismatch and preserve the logs. A passing preflight confirms only recorded HEADs, config checksum, presence of the driver archive, and the two object hashes; it does **not** validate the archive contents, dirty source trees, compiler, full Image, ABI/KMI, or runtime behavior.

## Gate B — If candidate is missing

Stop and record **workspace unavailable**. A fresh checkout does not recover the tested generated objects. A reconstruction must independently verify pinned sources, applied patches and dirty-tree changes, toolchain archive SHA256, resolved config, and compiled objects before it can be compared with the previous evidence. Treat that as a new candidate, not a continuation of an already-proven build.

## Gate C — Full Image (only after Gate A passes or a new candidate is validated)

Run **one** justified full Image/link attempt in the recovered build environment, preserving successful objects and logs. Check `vmlinux` link, BTF, Image existence and hashes, packaging, device/vendor ABI/KMI and boot/root/SUSFS/Wi-Fi behavior separately. Do not report **ready to flash** on a green Validate workflow or partial `ld.lld -r` link alone.

Current documented state: partial build verified; full Image, manager compatibility, and runtime **not verified**. Track blockers in issue #19.

## Gate D — Evidence completeness before GitHub Actions

The JSON evidence records commit identities and checksums, but **does not contain a replayable patch manifest or a complete working-tree diff**. Treat `source_context.prerequisite_commits` as provenance pointers, not instructions to cherry-pick those commits blindly. The config blob identifiers likewise do not reconstruct the kernel working tree.

Before scheduling a candidate-only manual Actions run, require a reviewable, ordered manifest of every applied kernel/KSUN/SUSFS patch (source URL, immutable revision, expected SHA256, application order), all local modifications, the toolchain download URL and SHA256, and the exact commands used to resolve `.config`. Verify each input *before* any compilation; stop on missing or mismatched inputs. Do not use floating branch tips, `curl | bash`, or `git apply` without checking downloaded content. Do not assume the recorded `driver_archive_member_sha256` verifies `built-in.a` as a whole.

If the historical workspace and patch provenance cannot be recovered, mark the candidate **not reproducible** and build a newly versioned candidate from independently pinned inputs. A green source-only Validate workflow does not waive these requirements. Keep production `build.yml` and `build.sh` KSUN+SUSFS guards intact.

Verified upstream provenance (GitHub API, 2026-10-15): `source_context.prerequisite_commits.ntsync` (`41ae18b...`) belongs to `WildKernels/kernel_patches`, **not** `ahmed-alnassif/GKI-Duchamp-6.1`; `bbg` (`a54e0dc...`) belongs to `vc-teahouse/Baseband-guard`; `nomount` (`7046c7a...`) belongs to `maxsteeel/nomount`. These are upstream commit references, **not proof** of an applied patch sequence or complete source replay.

## Gate E — SUSFS patch application isolation

Current `functions.sh` `apply_susfs_patches()` copies SUSFS files and uses `patch -p1 --fuzz=3`; its main patch failure can fall through except for a 5.15-specific fallback. This is **not an acceptable fail-closed replay mechanism** for the pinned KSUN+SUSFS 6.1 candidate. Do not modify this shared helper as a shortcut: other root-manager variants use it.

For a future **isolated** candidate replay, apply only checksum-verified patches in recorded order using `git apply --check` followed by `git apply` with no fuzz; stop on the first failure, preserve the exact rejection/log, and compare the resulting tracked changes and `.config` with recorded evidence. No production workflow change or build authorization is implied.

## Gate F — Kernel-patched SUSFS only (owner decision)

The selected integration is **KernelSU Next built-in + SUSFS patched into the kernel source**. SUSFS LKM is explicitly out of scope. Do not build, package, load, or fall back to `susfs_guard_lkm.ko`; the `kernel/susfs/` directory in the pinned KSUN upstream is a separate LKM implementation, **not** a source list for this candidate. Its presence does not prove that kernel-patched SUSFS works.

The pinned KSUN `kernel/core/init.c` calls `susfs_init()` from `<linux/susfs.h>` under `CONFIG_KSU_SUSFS`, and blacklists `susfs_guard_lkm`. This is consistent with selecting the built-in path but is **not** proof of full link or runtime compatibility.

Before patch replay, verify the actual kernel-patch implementation provides every referenced symbol with matching signatures. In particular, the locked companion adjustment introduces `ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr, size_t *count_ptr)` and `ksu_is_init_rc_hook_enabled` references in the SUSFS kernel patch; confirm both providers in the pinned built-in KSUN/kernel source before applying. Do not silently substitute LKM hooks or add a guessed shim. If providers are absent or signatures differ, stop and document the incompatibility.

Verified pinned KSUN provider (GitHub source inspection, commit `2f858cb292265795dee2807759cec2eb8a7d79b1`): `kernel/runtime/ksud_integration.c:36` defines `ksu_is_init_rc_hook_enabled` using `DEFINE_STATIC_KEY_TRUE`, and `:533` defines `ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr, size_t *count_ptr)`. This matches the companion patch's declaration and call shape. This resolves the **source-level symbol presence/signature gate only**; it does not establish that the final kernel patch applies, that full linking succeeds, or that the runtime hook behaves correctly. Keep the kernel-patched built-in implementation; no LKM fallback.

Namespace fix overlap: `ksun-6.1-companion-adjustments.patch` already incorporates the `susfs_fs_namespace_fix.patch` hunk. Never replay both blindly. The two `task_mmu.c` fixes target different source contexts; select neither without matching the exact pinned kernel source and recording its provenance.

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

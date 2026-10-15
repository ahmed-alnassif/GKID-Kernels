# KSUN + SUSFS 6.1 — isolated candidate plan

Status: **V2 CORE SOURCE INTEGRATED / NOT READY FOR COMPILATION OR FLASH**.
Scope: cogan17/Cogan branch dev, GKI Android 14 / kernel 6.1.

## Source identities
- Kernel: `a7ba124af5a535078d3f83b3e145f9cc8ec651b8`.
- KSUN (pershoot): `2f858cb292265795dee2807759cec2eb8a7d79b1`.
- Historical SUSFS lock: `a9bb4dd3ed248ada636b480bfdff70af704f1463`, not recovered. Its lock and partial-build evidence remain unchanged.
- V2 explicitly selects the owner-uploaded four-file source set. Three files match historical expected hashes; `susfs.c` instead hashes to `5521aa600f6df698e1d5e31df72e3557a36d33c161bd65dcafe5788fb56a7fa7`. The old expected hash is retained. There was never a verified four-of-four match against the historical manifest.
- Owner-reported upstream provenance is Simonpunk `92aab7f579e9fb440a43e387c13bff519af13462`; that commit was not independently downloaded this session. Actual v2 input identity is enforced by SHA256 of the preserved uploaded bytes.
- V2 lock: `configs/ksun-susfs-6.1-v2.lock.json`. API review: `ksun-susfs-6.1-api-review.md`. Actual integration evidence: `ksun-susfs-6.1-v2-integration.json`.

## Completed for v2 — reuse these results
1. Inspected signatures, linkage, configuration branches and built-in providers. The existing locked adjustment resolves the raw patch's one-argument read hook; setresuid's three-argument SUSFS branch and the credential/init interfaces match. All 14 SUSFS command handlers exist with matching interfaces.
2. Independently verified the exact clean kernel and KSUN checkouts and uploaded companion hashes. Selected v2 explicitly without overwriting historical provenance.
3. Prepared the original SUSFS patch using the existing locked delta; original and delta bytes are retained. Prepared SHA256 remains `c9e79c169c42ddae58ce92318a5ae59dcc6b3142849833c79c02059a4d25c46b`.
4. Created new detached local kernel and KSUN worktrees. Replayed driver Makefile/Kconfig/symlink integration, the prepared main patch, and the three companion files as an ordered three-patch series. The replay preflighted the entire series against a disposable index before applying it. This is a new full core-source integration check, not a repeat of the earlier isolated main-patch check.
5. Replayed one candidate-only KSUN Kbuild patch removing automatic Git fetch/version discovery. Version 33365 and tag v3.4.2 were independently checked using complete local history and the immutable tag commit.
6. Recorded kernel tree `7e2b5164757d23fe0fbe3cd81ebec264769a0542` and KSUN tree `2fd43a2d0ef0e1750102348869dd1152d306afb1`, full integration diff hashes, replay manifests and local logs. Five offline worktree preparation tests initially passed; the archive interface and its ten tests from concurrent commit `7dcdef0` are preserved in the same script and suite. No Actions or PR was created.

## Reproducible local preparation

The actual ordered replay manifests and all four emitted patches are preserved under `kernel-patches/susfs/6.1-v2/replay/`. Unlike the older evidence inventory JSON, `kernel-replay.json` and `ksun-replay.json` have the schema accepted by `scripts/ksun_susfs_replay.py`; each applies to its own source tree only. Do not reapply them to the already integrated worktrees.

When the existing v2 worktrees are available, inspect their recorded result and continue from them. If they have been lost, use clean local checkouts at the exact pins with all needed Git objects and complete KSUN history plus the verified tag, then run once from the Cogan root:

```sh
python3 scripts/prepare_ksun_susfs_candidate.py --locked-worktrees \
  /absolute/path/to/clean-kernel \
  /absolute/path/to/clean-ksun \
  /absolute/path/to/new-candidate-directory
```

The script is offline, rejects existing output directories, validates reviewed inputs, creates isolated worktrees, preserves the first failure, and never starts a build. An input or replay failure must be investigated before retrying. Original input trees are not patched. The separate historical `ksun_susfs_preflight.py` is not a v2 preflight.

## Remaining compilation gates
1. Inspect and pin NoMount and its transitive source inputs for the owner's requested bundle. It is not present in this core-source candidate. BBG is also outside this core replay; never execute floating installers to fill either gap.
2. Pin the compiler archive URL and verify actual downloaded bytes. The historical toolchain checksum alone does not verify a new download.
3. Generate the new `.config` with the pinned compiler, recording exact commands, configuration inputs, resolved values and hash. `configs/ksun-susfs-6.1-v2.config` is only a proposed core fragment with Full LTO/CFI and NTSync disabled; it is not a resolved configuration or final NoMount bundle. Never import shared `features.config`, which still requests NTSync.
4. Use a fresh output directory for clean LTO. Record KSUN version/tag flags during the first justified isolated compile, then inspect its first failure before any retry. Full Image/link, BTF, packaging, manager, vendor ABI/KMI and device runtime are later separate gates.

## Production safety
- Production KSUN v3.4.2 code and both KSUN+SUSFS build guards remain unchanged.
- No SUSFS LKM, NTSync or DroidSpaces integration. No automatic upstream update, Actions dispatch, release, flashing, or production switch.
- No historical object, config or partial-link success is claimed for v2.
- Do not rerun green historical Actions or repeat completed source checks without a changed input or concrete failure to investigate.

## Concurrent archive preparation retained

Branch dev received commit `7dcdef0` during this work. Its archive interface
`python3 scripts/prepare_ksun_susfs_candidate.py SOURCE.zip NEW_BUNDLE` remains
available, including its optional adjacent-checkout staging and ten tests. Its
`configs/ksun-susfs-6.1-candidate-v2.json` controls archive packaging; the distinct
`configs/ksun-susfs-6.1-v2.lock.json` controls the stronger offline worktree route,
reviewed-file SHA256 checks and version patch. Both select the same exact kernel,
KSUN and SUSFS file bytes. Use **--locked-worktrees** for the actual integration
recorded here; do not confuse the earlier two-file fixture with the completed
full core-source stage. No concurrent commit was overwritten.

Post-merge validation: ten archive-interface tests and five offline worktree tests passed. Only the affected five were rerun after correcting a helper-name merge error. The already successful complete core-source replay was not repeated.

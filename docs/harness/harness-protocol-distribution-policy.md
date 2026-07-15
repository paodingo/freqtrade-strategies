# Harness Protocol Static Distribution Policy

## Status and boundary

P4A defines a source-controlled, deterministic distribution description for the
P1 Protocol Core and P2 Project Mapping artifacts. It does not publish those
artifacts and does not authorize a consumer rollout. The implementation is
`static_distribution_only`: it adds no shared Runtime, CLI, package, plugin,
skill, Role Pack, network operation, sibling-repository write, project business
execution, or Campaign execution.

The canonical v0.x owner is an exact commit in
`https://github.com/paodingo/freqtrade-strategies.git`. For distribution v0.1,
`harness/distribution/v0.1/release-manifest.json` binds the frozen 15-file input
set to source commit `6363b7f8352a53cbcd709a4d3d6b5c0bc7ba3b93`.
That commit identifies the canonical input snapshot; it is intentionally not a
self-reference to the later commit that adds the generated release manifest.

## Distribution contents

The manifest has two ordered components:

1. `protocol-core`: the P1 schema, P1 manifest, and five P1 synthetic fixtures.
2. `project-mappings`: the P2 schema, P2 manifest, three frozen project mapping
   descriptors, and three P2 synthetic failure fixtures.

The manifest is closed and records each artifact's repo-relative POSIX path,
component, media type, normalized byte count, and fingerprint. No artifact may
be added, omitted, or reordered without generating a different manifest and
obtaining a new explicit approval.

## Portable fingerprint profile

`sha256-text-lf-v1` is the only supported profile:

- input must be UTF-8 text without a BOM;
- invalid UTF-8 is an error;
- CRLF and lone CR are normalized to LF;
- all other content is preserved;
- duplicate JSON object keys are an error;
- SHA-256 is computed over the normalized UTF-8 bytes; and
- an unknown profile fails closed.

The P1 and P2 fingerprints created before P4A keep their historical,
project-local meaning. P4A does not silently reinterpret or rewrite them.

## Source-side build and verification

From the repository root, using the approved local Python environment:

```powershell
.\.venv-freqtrade\Scripts\python.exe scripts/build_harness_protocol_distribution.py --check
.\.venv-freqtrade\Scripts\python.exe scripts/verify_harness_protocol_distribution.py
```

The builder reads only the frozen 15-file set plus the local fingerprint profile
and writes only the exact release-manifest path when run without `--check`. The
verifier validates the closed schema, deterministic reconstruction, P1/P2
membership relationships, and source-side-only imports. Neither script copies
files to a consumer or performs network, project Runtime, or sibling-repository
operations.

Portable exit semantics are:

- `0`: passed;
- `1`: blocked because the checked distribution does not match its contract;
- `2`: tool or parser error that prevented a trustworthy result.

## Upgrade and rollback

There is no auto-update. A change to the source commit, any artifact
fingerprint, or component membership invalidates the current approval and
requires explicit project approval for a new distribution candidate.

A future consumer may roll back only by explicitly pinning a previously
approved release. Rollback must preserve the consumer's project-local Runtime;
automatic cleanup, overwrite, and migration are outside P4A.

## Gate B evidence and stop condition

P4A Gate B requires all of the following before this implementation can be
called ready for a later distribution decision:

- exact 12-path implementation diff;
- deterministic 15-artifact manifest and `sha256-text-lf-v1` fingerprints;
- P1+P2+P4A focused tests, standard readiness checks, and clean-worktree
  portable baseline evidence;
- protected trading/business surface diff of zero;
- unchanged sibling repositories; and
- an independent review from a fresh detached worktree.

Passing Gate B still does not publish, tag, release, copy, install, or roll out
anything. Those actions require a separate plan and separate explicit approval.

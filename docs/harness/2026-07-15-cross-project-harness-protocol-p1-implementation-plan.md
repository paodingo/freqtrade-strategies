# Cross-Project Harness Protocol P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Implement approved Stage P1 as a language-neutral JSON protocol, five synthetic golden fixtures, and an isolated conformance suite without importing or changing any of the three project runtimes.

**Architecture:** Store the protocol under one versioned artifact root. Validate individual artifacts with JSON Schema Draft 2020-12 and test cross-artifact semantics with Python `unittest` plus the existing `jsonschema` dependency. Expand repository guardrails only for the 10 exact P1 files; no broad Harness surface is introduced.

**Tech Stack:** JSON Schema Draft 2020-12, JSON, Python 3.12, `unittest`, `jsonschema` 4.x, Node.js guard scripts, PowerShell readiness wrapper.

## Global Constraints

- Authoritative design: `docs/harness/2026-07-15-cross-project-harness-protocol-design.md`.
- Work only in `D:\code\freqtrade-strategies-clean` on the approved task branch.
- Before each task, require `git status --short --untracked-files=all` to be empty; otherwise stop without writing.
- Stage only paths named in the current task. Never use `git add -A`, `git add .`, broad globs, stash, reset, clean, or unrelated remediation.
- Do not edit `D:\code\ChinaSectorRadar` or `D:\book\rehab-intervention` in P1.
- Do not add a CLI, package, plugin, executor, Adapter, Role Pack, state backend, database, network call, production integration, or model-provider interface.
- Do not add project-domain literals to `harness/protocol/v0.1/**`.
- Preserve `0 -> passed`, `1 -> blocked`, `2 -> error`.
- Preserve `business_readiness` independently from `harness_completion`.
- Use synthetic, non-secret fixture data only.
- Run Python with `.\.venv-freqtrade\Scripts\python.exe -B`; set `PYTHONDONTWRITEBYTECODE=1` for final verification.
- Commit after each task and stop for the review checkpoint required by the selected execution skill.

### Current Pre-Implementation Baseline Condition

Plan-writing verification on `2026-07-15` established the following current evidence:

- `scripts/run_agent_readiness_checks.ps1` passes all three guards for the two plan-document paths.
- `clean_worktree_portable` completes in approximately 793 seconds; its fixture pack passes and `versioned_worktree_unchanged` is `true`.
- The profile currently reports two new failures with one shared cause: `portable_runtime_file_set_mismatch:missing=0:extra=418`.
- An exact read-only audit found 418 files, all under `.venv-freqtrade/**/__pycache__/*.pyc`, created on `2026-07-14` before this plan-writing run.

This plan does not authorize deleting or rewriting the local runtime. Before Task 1 implementation begins, use a clean rehydrated portable runtime or obtain separate authority for exact cache cleanup, then rerun `clean_worktree_portable`. Do not reclassify the two errors as a passing baseline, and do not hide the repository's separately recognized historical Python/Node baseline debt.

## Exact Planned File Surface

Create:

```text
harness/protocol/v0.1/harness-protocol.schema.json
harness/protocol/v0.1/protocol-manifest.json
harness/protocol/v0.1/fixtures/normal.json
harness/protocol/v0.1/fixtures/governed-block.json
harness/protocol/v0.1/fixtures/tool-error.json
harness/protocol/v0.1/fixtures/authority-mismatch.json
harness/protocol/v0.1/fixtures/known-baseline-debt.json
tests/test_harness_protocol_guard_contract.py
tests/test_harness_protocol_contracts.py
tests/test_harness_protocol_conformance.py
```

Modify:

```text
scripts/guard_harness_diff.js
docs/harness/change_surface_matrix.md
```

No other implementation path is authorized by this plan.

## Task 1: Lock the Exact P1 Guard Contract

**Files:**

- Create: `tests/test_harness_protocol_guard_contract.py`
- Modify: `scripts/guard_harness_diff.js`
- Modify: `docs/harness/change_surface_matrix.md`

### Step 1: Verify the repository gate

Run:

```powershell
git branch --show-current
git status --short --untracked-files=all
```

Expected: approved branch and empty status. Stop on any mismatch.

### Step 2: Write the failing guard test

Create `tests/test_harness_protocol_guard_contract.py`:

```python
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO_ROOT / "scripts" / "guard_harness_diff.js"
EXPECTED_P1_PATHS = {
    "harness/protocol/v0.1/harness-protocol.schema.json",
    "harness/protocol/v0.1/protocol-manifest.json",
    "harness/protocol/v0.1/fixtures/normal.json",
    "harness/protocol/v0.1/fixtures/governed-block.json",
    "harness/protocol/v0.1/fixtures/tool-error.json",
    "harness/protocol/v0.1/fixtures/authority-mismatch.json",
    "harness/protocol/v0.1/fixtures/known-baseline-debt.json",
    "tests/test_harness_protocol_guard_contract.py",
    "tests/test_harness_protocol_contracts.py",
    "tests/test_harness_protocol_conformance.py",
}


class HarnessProtocolGuardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard_source = GUARD_PATH.read_text(encoding="utf-8")

    def test_every_p1_path_is_allowlisted_as_an_exact_path(self):
        for path in EXPECTED_P1_PATHS:
            with self.subTest(path=path):
                self.assertEqual(
                    self.guard_source.count(f'{{ exact: "{path}" }}'),
                    1,
                )

    def test_no_broad_protocol_prefix_or_regex_is_allowlisted(self):
        patterns = (
            r'\{\s*prefix:\s*["\']harness/protocol/',
            r'\{\s*regex:\s*/[^\n]*harness\\?/protocol',
        )
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.guard_source))


if __name__ == "__main__":
    unittest.main()
```

Run and expect the exact-path test to fail because the entries do not exist yet:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract -v
```

### Step 3: Add exactly 10 low-risk entries

Add these entries to `LOW_RISK_SURFACES` in `scripts/guard_harness_diff.js`:

```javascript
  { exact: "harness/protocol/v0.1/harness-protocol.schema.json" },
  { exact: "harness/protocol/v0.1/protocol-manifest.json" },
  { exact: "harness/protocol/v0.1/fixtures/normal.json" },
  { exact: "harness/protocol/v0.1/fixtures/governed-block.json" },
  { exact: "harness/protocol/v0.1/fixtures/tool-error.json" },
  { exact: "harness/protocol/v0.1/fixtures/authority-mismatch.json" },
  { exact: "harness/protocol/v0.1/fixtures/known-baseline-debt.json" },
  { exact: "tests/test_harness_protocol_guard_contract.py" },
  { exact: "tests/test_harness_protocol_contracts.py" },
  { exact: "tests/test_harness_protocol_conformance.py" },
```

Do not add a `prefix`, `regex`, or general `harness/**` permission.

### Step 4: Document the new surface

Add one row to `docs/harness/change_surface_matrix.md` identifying:

- the two exact protocol files, five exact fixture files, and three exact test files;
- risk classification `low, P1-only`;
- allowed purpose: schema, manifest, synthetic fixtures, isolated tests;
- explicitly absent authority: runtime, Adapter, Role Pack, sibling migration, network, secret, data, trading, database, scheduler, and deployment;
- verification: exact-path guard test, protocol tests, standard readiness, and clean-worktree baseline.

### Step 5: Verify and commit

Run:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract -v
node scripts/guard_harness_diff.js
git add -- scripts/guard_harness_diff.js docs/harness/change_surface_matrix.md tests/test_harness_protocol_guard_contract.py
git diff --cached --name-only
git diff --cached --check
git commit -m "harness: authorize exact protocol P1 surface"
```

Expected: 2 tests pass; guard reports `OK`; staged paths are exactly the three task files. Stop after commit.

## Task 2: Implement the Core Schema and Normal Fixture

**Files:**

- Create: `harness/protocol/v0.1/harness-protocol.schema.json`
- Create: `harness/protocol/v0.1/fixtures/normal.json`
- Create: `tests/test_harness_protocol_contracts.py`

### Step 1: Verify clean state, then write the failing contract test

Require empty `git status --short --untracked-files=all`, then create `tests/test_harness_protocol_contracts.py`:

```python
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "harness" / "protocol" / "v0.1"
SCHEMA_PATH = PROTOCOL_ROOT / "harness-protocol.schema.json"
NORMAL_FIXTURE_PATH = PROTOCOL_ROOT / "fixtures" / "normal.json"

EXPECTED_SCHEMA_VERSIONS = {
    "ProjectBinding": "harness-project-binding-v0.1",
    "PhaseAuthority": "harness-phase-authority-v0.1",
    "CapabilityPolicy": "harness-capability-policy-v0.1",
    "RoleContract": "harness-role-contract-v0.1",
    "TaskManifest": "harness-task-manifest-v0.1",
    "GateResult": "harness-gate-result-v0.1",
    "RunState": "harness-run-state-v0.1",
    "ApprovalRecord": "harness-approval-record-v0.1",
    "EscalationRecord": "harness-escalation-record-v0.1",
    "EvidenceBundle": "harness-evidence-bundle-v0.1",
}
EXPECTED_CONTRACTS = set(EXPECTED_SCHEMA_VERSIONS) | {"Budget"}


class HarnessProtocolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.normal_fixture = json.loads(
            NORMAL_FIXTURE_PATH.read_text(encoding="utf-8")
        )

    def test_schema_is_valid_draft_2020_12(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        Draft202012Validator.check_schema(self.schema)
        for name, definition in self.schema["$defs"].items():
            if definition.get("type") == "object":
                with self.subTest(closed_definition=name):
                    self.assertIs(
                        definition.get("additionalProperties"),
                        False,
                    )

    def test_schema_exposes_only_approved_contracts(self):
        public_defs = {
            name
            for name, definition in self.schema["$defs"].items()
            if "schema_version" in definition.get("properties", {})
        } | {"Budget"}
        self.assertEqual(public_defs, EXPECTED_CONTRACTS)
        self.assertEqual(
            {
                item["$ref"].removeprefix("#/$defs/")
                for item in self.schema["oneOf"]
            },
            EXPECTED_CONTRACTS - {"Budget"},
        )

    def test_schema_versions_are_exact(self):
        for contract, version in EXPECTED_SCHEMA_VERSIONS.items():
            with self.subTest(contract=contract):
                self.assertEqual(
                    self.schema["$defs"][contract]["properties"]["schema_version"],
                    {"const": version},
                )

    def test_normal_fixture_has_one_valid_artifact_per_root_contract(self):
        documents = self.normal_fixture["documents"]
        self.assertEqual(
            {document["contract"] for document in documents},
            set(EXPECTED_SCHEMA_VERSIONS),
        )
        self.assertEqual(len(documents), len(EXPECTED_SCHEMA_VERSIONS))
        for document in documents:
            target_schema = {
                "$schema": self.schema["$schema"],
                "$defs": self.schema["$defs"],
                "$ref": f"#/$defs/{document['contract']}",
            }
            with self.subTest(contract=document["contract"]):
                Draft202012Validator(target_schema).validate(
                    document["artifact"]
                )


if __name__ == "__main__":
    unittest.main()
```

Run the test. Expected: `FileNotFoundError` for `harness-protocol.schema.json`.

### Step 2: Create the Draft 2020-12 schema

Create `harness/protocol/v0.1/harness-protocol.schema.json` with:

- root `$schema` equal to `https://json-schema.org/draft/2020-12/schema`;
- root `$id` equal to `https://example.invalid/harness/protocol/v0.1/harness-protocol.schema.json`;
- root `oneOf` containing exactly the 10 versioned contracts, excluding nested `Budget`;
- `$defs` containing the exact helpers and contracts below;
- `additionalProperties: false` on every object definition;
- every field in each contract's row listed in `required`;
- arrays using `uniqueItems: true` where their identity is set-like.

Helper definitions:

| Definition | Exact constraint |
|---|---|
| `identifier` | string matching `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$` |
| `fingerprint` | string matching `^sha256:[a-f0-9]{64}$` |
| `timestamp` | non-empty string with `format: date-time` |
| `nonEmptyString` | string, `minLength: 1` |
| `repoPath` | non-empty relative path; reject drive-qualified, `/`, and UNC prefixes |
| `capability` | string matching `^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*$` |
| `reasonCode` | string matching `^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$` |
| `RuntimeEntry` | `entry_id`, `kind`, `command`; kind is `process`, `human`, `model`, or `project_local` |
| `StateBackend` | required `kind`, optional `location`; kind is `project_local`, `external`, or `none` |
| `ArtifactRef` | `artifact_id`, `path`, `fingerprint` |
| `ValidationCommand` | `command_id`, `command`, and exact mapping `{0: passed, 1: blocked, 2: error}` |
| `CommandResult` | `command_id`, `exit_code` in `0/1/2`, `outcome` in `passed/blocked/error` |

Public contract field matrix:

| Contract and exact `schema_version` | Required fields and constraints |
|---|---|
| `ProjectBinding` / `harness-project-binding-v0.1` | `protocol_version` const `0.1`; `project_id`; `project_root_identity`; non-empty `authority_sources`; `phase_source`; `policy_sources`; `runtime_entries`; `state_backend`; non-empty `evidence_roots`; `adapter_version` |
| `PhaseAuthority` / `harness-phase-authority-v0.1` | `phase_id`; `authority_fingerprint`; `approved_operations`; `forbidden_operations`; `protected_surfaces`; nullable `next_phase`; boolean `next_phase_requires_human_approval`; `effective_at` |
| `CapabilityPolicy` / `harness-capability-policy-v0.1` | `policy_id`; `allowed_capabilities`; `forbidden_capabilities`; `deny_unknown` const `true` |
| `RoleContract` / `harness-role-contract-v0.1` | `role_id`; `role_pack`; `accepted_input_contracts`; `produced_output_contracts`; `allowed_capabilities`; `forbidden_capabilities`; `approval_authority`; `self_approval_allowed` const `false`; `escalation_conditions` |
| `TaskManifest` / `harness-task-manifest-v0.1` | `task_id`; `project_id`; `phase_id`; `role_id`; `objective`; `input_bindings`; `allowed_paths`; `blocked_paths`; `capabilities`; `budgets`; at least one `validation_commands`; `expected_outputs`; `stop_conditions`; `required_approvals`; `authority_fingerprint` |
| `Budget` / nested, no `schema_version` | at least one of `max_attempts`, `max_tasks`, `max_wall_clock_seconds`, `max_changed_files`, `max_output_bytes`, `max_external_calls`, `max_data_accesses`; counts are non-negative except attempts/tasks/time, which are at least 1 |
| `GateResult` / `harness-gate-result-v0.1` | `gate_id`; `outcome`; `process_exit_code`; `reason_code`; `local_reason_code`; `evidence_refs` |
| `RunState` / `harness-run-state-v0.1` | `run_id`; `task_id`; `state` in `planned/ready/running/completed/stopped/failed/escalated`; boolean `resumable`; `updated_at` |
| `ApprovalRecord` / `harness-approval-record-v0.1` | `approval_id`; `approver_type`; `approved_action`; non-empty `bound_artifacts`; non-empty `bound_fingerprints`; `scope`; `decided_at`; `expiry_policy`; `approval_fingerprint` |
| `EscalationRecord` / `harness-escalation-record-v0.1` | `reason_code`; `blocked_action`; `current_phase`; `required_authority`; `evidence_refs`; `safe_resume_condition`; `created_at` |
| `EvidenceBundle` / `harness-evidence-bundle-v0.1` | `run_id`; `project_id`; `task_id`; `authority_snapshot`; `input_identities`; non-empty `gate_results`; non-empty `command_results`; `artifact_refs`; `known_baseline_debt`; `open_blockers`; `business_readiness` in `ready/blocked/degraded/unknown`; `harness_completion`; `final_run_state`; `generated_at` |

`ApprovalRecord.expiry_policy` is a closed `oneOf`: either `{kind: expires_at, expires_at: timestamp}` or `{kind: explicit_non_expiry, invalidation_rule: nonEmptyString}`. `harness_completion` and `final_run_state` accept `completed/stopped/failed/escalated` independently from `business_readiness`.

The schema validates shape only. Cross-field rules—path precedence, exit/outcome pairing, authority freshness, and completion/readiness independence—belong to Task 3 conformance tests.

### Step 3: Create the normal fixture

Create `harness/protocol/v0.1/fixtures/normal.json` with wrapper fields:

```json
{
  "fixture_version": "harness-protocol-fixture-v0.1",
  "case_id": "normal",
  "expected": {
    "outcome": "passed",
    "reason_code": "fixture_conforms"
  },
  "documents": []
}
```

Replace the empty `documents` array with exactly one minimal valid artifact for every root contract. Use only:

- synthetic IDs such as `synthetic.project`, `phase.p1`, `task.synthetic`, and `run.synthetic`;
- relative paths such as `authority/project.json`, `input/source.json`, and `out/result.json`;
- synthetic `sha256:` values with exactly 64 lower-case hex digits;
- `core.read_repository`, `core.run_validation`, `core.write_allowlisted_artifact`, and `deploy.publish` as generic capability examples;
- UTC timestamps on `2026-07-15`;
- `self_approval_allowed: false`;
- a valid explicit non-expiry policy;
- a passed `GateResult` with exit `0`;
- a completed `RunState`;
- an `EvidenceBundle` with both `business_readiness: ready` and `harness_completion: completed`.

Each item has exact wrapper shape:

```json
{
  "contract": "ProjectBinding",
  "artifact": {
    "schema_version": "harness-project-binding-v0.1"
  }
}
```

The shown artifact is a shape illustration, not a complete artifact; populate every required field from the matrix before running tests.

### Step 4: Verify and commit

Run:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract tests.test_harness_protocol_contracts -v
git add -- harness/protocol/v0.1/harness-protocol.schema.json harness/protocol/v0.1/fixtures/normal.json tests/test_harness_protocol_contracts.py
git diff --cached --name-only
git diff --cached --check
git commit -m "harness: add protocol v0.1 contracts"
```

Expected: 6 tests pass; staged paths are exactly the three task files. Stop after commit.

## Task 3: Add Failure-Semantics Fixtures and Conformance Tests

**Files:**

- Create: `harness/protocol/v0.1/fixtures/governed-block.json`
- Create: `harness/protocol/v0.1/fixtures/tool-error.json`
- Create: `harness/protocol/v0.1/fixtures/authority-mismatch.json`
- Create: `harness/protocol/v0.1/fixtures/known-baseline-debt.json`
- Create: `tests/test_harness_protocol_conformance.py`

### Step 1: Verify clean state, then write the failing tests

Require empty `git status --short --untracked-files=all`, then create `tests/test_harness_protocol_conformance.py`:

```python
import json
import unittest
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "harness" / "protocol" / "v0.1"
FIXTURE_ROOT = PROTOCOL_ROOT / "fixtures"
FIXTURE_CASES = {
    "normal": ("passed", "fixture_conforms"),
    "governed-block": ("blocked", "path_blocked"),
    "tool-error": ("error", "environment_unavailable"),
    "authority-mismatch": ("blocked", "authority_mismatch"),
    "known-baseline-debt": ("passed", "known_baseline_debt_preserved"),
}
PORTABLE_EXIT_MAPPING = {0: "passed", 1: "blocked", 2: "error"}


class HarnessProtocolConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (PROTOCOL_ROOT / "harness-protocol.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.fixtures = {
            case_id: json.loads(
                (FIXTURE_ROOT / f"{case_id}.json").read_text(encoding="utf-8")
            )
            for case_id in FIXTURE_CASES
        }

    def documents(self, case_id, contract):
        return [
            document["artifact"]
            for document in self.fixtures[case_id]["documents"]
            if document["contract"] == contract
        ]

    def test_every_document_conforms_to_declared_contract(self):
        for case_id, fixture in self.fixtures.items():
            for document in fixture["documents"]:
                target_schema = {
                    "$schema": self.schema["$schema"],
                    "$defs": self.schema["$defs"],
                    "$ref": f"#/$defs/{document['contract']}",
                }
                with self.subTest(
                    case_id=case_id,
                    contract=document["contract"],
                ):
                    Draft202012Validator(target_schema).validate(
                        document["artifact"]
                    )

    def test_fixture_outcomes_are_exact(self):
        for case_id, (outcome, reason_code) in FIXTURE_CASES.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(
                    self.fixtures[case_id]["expected"],
                    {"outcome": outcome, "reason_code": reason_code},
                )

    def test_portable_exit_mapping_is_preserved(self):
        for case_id in FIXTURE_CASES:
            gates = self.documents(case_id, "GateResult")
            bundles = self.documents(case_id, "EvidenceBundle")
            gates.extend(
                gate for bundle in bundles for gate in bundle["gate_results"]
            )
            commands = [
                result
                for bundle in bundles
                for result in bundle["command_results"]
            ]
            for result in gates + commands:
                exit_code = result.get(
                    "process_exit_code",
                    result.get("exit_code"),
                )
                with self.subTest(case_id=case_id, result=result):
                    self.assertEqual(
                        result["outcome"],
                        PORTABLE_EXIT_MAPPING[exit_code],
                    )

    def test_blocked_path_overrides_allowed_path(self):
        fixture = self.fixtures["governed-block"]
        task = self.documents("governed-block", "TaskManifest")[0]
        gate = self.documents("governed-block", "GateResult")[0]
        attempted = PurePosixPath(fixture["context"]["attempted_path"])
        allowed = PurePosixPath(task["allowed_paths"][0])
        blocked = PurePosixPath(task["blocked_paths"][0])
        self.assertTrue(attempted.is_relative_to(allowed))
        self.assertTrue(attempted.is_relative_to(blocked))
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("blocked", 1, "path_blocked"),
        )

    def test_tool_failure_is_error_not_governed_block(self):
        gate = self.documents("tool-error", "GateResult")[0]
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("error", 2, "environment_unavailable"),
        )

    def test_authority_mismatch_fails_closed(self):
        fixture = self.fixtures["authority-mismatch"]
        task = self.documents("authority-mismatch", "TaskManifest")[0]
        gate = self.documents("authority-mismatch", "GateResult")[0]
        self.assertNotEqual(
            task["authority_fingerprint"],
            fixture["context"]["current_authority_fingerprint"],
        )
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("blocked", 1, "authority_mismatch"),
        )

    def test_known_debt_preserves_business_block_and_completion(self):
        evidence = self.documents("known-baseline-debt", "EvidenceBundle")[0]
        self.assertTrue(evidence["known_baseline_debt"])
        self.assertTrue(evidence["open_blockers"])
        self.assertEqual(evidence["business_readiness"], "blocked")
        self.assertEqual(evidence["harness_completion"], "completed")
        self.assertEqual(evidence["final_run_state"], "completed")


if __name__ == "__main__":
    unittest.main()
```

Run and expect setup to fail on the first missing fixture:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_conformance -v
```

### Step 2: Create the exact four cases

Each fixture uses the same wrapper as `normal.json`. Populate documents exactly as follows; every artifact must satisfy its Task 2 contract.

| File | Context | Required documents | Exact expected semantics |
|---|---|---|---|
| `governed-block.json` | `attempted_path: workspace/protected/output.json` | `TaskManifest`, `GateResult` | manifest allows `workspace`, blocks `workspace/protected`, requests `core.write_allowlisted_artifact`; gate is `blocked`, exit `1`, reason `path_blocked`, local reason `blocked_path_overrides_allowlist` |
| `tool-error.json` | none | `GateResult` | gate is `error`, exit `2`, reason `environment_unavailable`, local reason `validator_process_not_available` |
| `authority-mismatch.json` | `current_authority_fingerprint` uses 64 hex `3` digits | `TaskManifest`, `GateResult` | manifest binds a different fingerprint using 64 hex `2` digits; gate is `blocked`, exit `1`, reason `authority_mismatch`, local reason `bound_authority_is_stale` |
| `known-baseline-debt.json` | none | `EvidenceBundle` | nested gate and command are `passed/0`; debt and blocker arrays are non-empty; `business_readiness` is `blocked`; `harness_completion` and `final_run_state` are `completed` |

Use these exact fixture outcomes:

```json
{
  "governed-block": {
    "outcome": "blocked",
    "reason_code": "path_blocked"
  },
  "tool-error": {
    "outcome": "error",
    "reason_code": "environment_unavailable"
  },
  "authority-mismatch": {
    "outcome": "blocked",
    "reason_code": "authority_mismatch"
  },
  "known-baseline-debt": {
    "outcome": "passed",
    "reason_code": "known_baseline_debt_preserved"
  }
}
```

All missing required fields use the same synthetic IDs, relative paths, fingerprints, timestamps, validation mapping, and generic capabilities established by the normal fixture. Do not introduce a real project name, real repository identity, production path, or secret-like value.

### Step 3: Verify and commit

Run:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract tests.test_harness_protocol_contracts tests.test_harness_protocol_conformance -v
git add -- harness/protocol/v0.1/fixtures/governed-block.json harness/protocol/v0.1/fixtures/tool-error.json harness/protocol/v0.1/fixtures/authority-mismatch.json harness/protocol/v0.1/fixtures/known-baseline-debt.json tests/test_harness_protocol_conformance.py
git diff --cached --name-only
git diff --cached --check
git commit -m "test: add harness protocol conformance fixtures"
```

Expected: `2 guard + 4 contract + 7 conformance = 13` tests pass; staged paths are exactly the five task files. Stop after commit.

## Task 4: Publish the Manifest and Prove Isolation

**Files:**

- Create: `harness/protocol/v0.1/protocol-manifest.json`
- Modify: `tests/test_harness_protocol_contracts.py`
- Modify: `tests/test_harness_protocol_conformance.py`

### Step 1: Verify clean state, then add the failing manifest test

Require empty `git status --short --untracked-files=all`.

In `tests/test_harness_protocol_contracts.py`, add:

```python
MANIFEST_PATH = PROTOCOL_ROOT / "protocol-manifest.json"
```

In `setUpClass`, load it:

```python
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
```

Add:

```python
    def test_manifest_indexes_exact_protocol_surface(self):
        self.assertEqual(self.manifest["protocol_version"], "0.1")
        self.assertEqual(
            self.manifest["schema_path"],
            "harness-protocol.schema.json",
        )
        self.assertEqual(
            self.manifest["portable_exit_mapping"],
            {"0": "passed", "1": "blocked", "2": "error"},
        )
        self.assertEqual(
            {
                (
                    fixture["path"],
                    fixture["outcome"],
                    fixture["reason_code"],
                )
                for fixture in self.manifest["fixtures"]
            },
            {
                ("fixtures/normal.json", "passed", "fixture_conforms"),
                ("fixtures/governed-block.json", "blocked", "path_blocked"),
                ("fixtures/tool-error.json", "error", "environment_unavailable"),
                ("fixtures/authority-mismatch.json", "blocked", "authority_mismatch"),
                (
                    "fixtures/known-baseline-debt.json",
                    "passed",
                    "known_baseline_debt_preserved",
                ),
            },
        )
```

Run the contract module and expect `FileNotFoundError` for `protocol-manifest.json`.

### Step 2: Create the exact manifest

Create `harness/protocol/v0.1/protocol-manifest.json`:

```json
{
  "manifest_version": "harness-protocol-manifest-v0.1",
  "protocol_version": "0.1",
  "schema_path": "harness-protocol.schema.json",
  "fixture_version": "harness-protocol-fixture-v0.1",
  "portable_exit_mapping": {
    "0": "passed",
    "1": "blocked",
    "2": "error"
  },
  "contracts": [
    "ProjectBinding",
    "PhaseAuthority",
    "CapabilityPolicy",
    "RoleContract",
    "TaskManifest",
    "Budget",
    "GateResult",
    "RunState",
    "ApprovalRecord",
    "EscalationRecord",
    "EvidenceBundle"
  ],
  "fixtures": [
    {
      "path": "fixtures/normal.json",
      "outcome": "passed",
      "reason_code": "fixture_conforms"
    },
    {
      "path": "fixtures/governed-block.json",
      "outcome": "blocked",
      "reason_code": "path_blocked"
    },
    {
      "path": "fixtures/tool-error.json",
      "outcome": "error",
      "reason_code": "environment_unavailable"
    },
    {
      "path": "fixtures/authority-mismatch.json",
      "outcome": "blocked",
      "reason_code": "authority_mismatch"
    },
    {
      "path": "fixtures/known-baseline-debt.json",
      "outcome": "passed",
      "reason_code": "known_baseline_debt_preserved"
    }
  ],
  "scope": {
    "includes": [
      "language-neutral contracts",
      "synthetic golden fixtures",
      "isolated conformance tests"
    ],
    "excludes": [
      "shared executable runtime",
      "command line interface",
      "project adapters",
      "role packs",
      "production integration"
    ]
  }
}
```

### Step 3: Add isolation tests

Add `import ast` to `tests/test_harness_protocol_conformance.py`, then add:

```python
    def test_protocol_tests_do_not_import_project_runtime(self):
        allowed_top_level_modules = {
            "ast",
            "json",
            "pathlib",
            "re",
            "unittest",
            "jsonschema",
        }
        test_paths = (
            REPO_ROOT / "tests" / "test_harness_protocol_guard_contract.py",
            REPO_ROOT / "tests" / "test_harness_protocol_contracts.py",
            REPO_ROOT / "tests" / "test_harness_protocol_conformance.py",
        )
        for test_path in test_paths:
            tree = ast.parse(test_path.read_text(encoding="utf-8"))
            imported_modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".", 1)[0])
            with self.subTest(test_path=test_path.name):
                self.assertLessEqual(
                    imported_modules,
                    allowed_top_level_modules,
                )

    def test_protocol_json_contains_no_project_domain_literals(self):
        forbidden_literals = {
            "freqtrade",
            "binance",
            "btc/usdt",
            "chinasectorradar",
            "rehab-intervention",
            "prisma",
            "regimeaware",
            "holdout",
            "scheduler",
            "strategy_family",
        }
        json_paths = sorted(PROTOCOL_ROOT.rglob("*.json"))
        self.assertEqual(len(json_paths), 7)
        for json_path in json_paths:
            content = json_path.read_text(encoding="utf-8").lower()
            for literal in forbidden_literals:
                with self.subTest(path=json_path.name, literal=literal):
                    self.assertNotIn(literal, content)
```

This proves import and vocabulary isolation; it does not select Python as a future shared runtime.

### Step 4: Run focused, readiness, and baseline verification

Run:

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract tests.test_harness_protocol_contracts tests.test_harness_protocol_conformance -v
.\scripts\run_agent_readiness_checks.ps1
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-freqtrade\Scripts\python.exe -B scripts/verify_test_baseline.py --run --profile clean_worktree_portable
Remove-Item Env:PYTHONDONTWRITEBYTECODE
git status --short --untracked-files=all
```

Expected:

- `2 guard + 5 contract + 9 conformance = 16` tests pass;
- all three readiness guards report `OK`;
- baseline exits `0` with `"errors": []` and `"versioned_worktree_unchanged": true`;
- status contains only the three Task 4 paths and no cache or unrelated file.

If baseline debt is reported, preserve and report it exactly; do not edit unrelated files or weaken a gate.

### Step 5: Commit and verify the complete P1 state

Run:

```powershell
git add -- harness/protocol/v0.1/protocol-manifest.json tests/test_harness_protocol_contracts.py tests/test_harness_protocol_conformance.py
git diff --cached --name-only
git diff --cached --check
git commit -m "test: prove harness protocol isolation"
.\.venv-freqtrade\Scripts\python.exe -B -m unittest tests.test_harness_protocol_guard_contract tests.test_harness_protocol_contracts tests.test_harness_protocol_conformance -v
.\scripts\run_agent_readiness_checks.ps1
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-freqtrade\Scripts\python.exe -B scripts/verify_test_baseline.py --run --profile clean_worktree_portable
Remove-Item Env:PYTHONDONTWRITEBYTECODE
git diff --name-only HEAD~4..HEAD
git status --short --untracked-files=all
```

Expected:

- staged paths before commit are exactly the three Task 4 files;
- final tests and readiness pass;
- baseline passes without mutating the worktree;
- the four-commit diff contains exactly the 12 planned implementation paths: 10 created files plus two modified guard/documentation files;
- final status is empty.

## Final Review Checklist

- Draft 2020-12 schema exposes exactly 10 root contracts plus nested `Budget`.
- Every object contract is closed to unknown fields.
- Manifest indexes exactly five fixtures and the portable exit map.
- Every fixture document validates against its declared contract.
- `blocked_paths` wins over `allowed_paths`.
- Tool/environment failure is `error/2`, not `blocked/1`.
- Authority mismatch is `blocked/1` with `authority_mismatch`.
- Known debt stays visible while Harness completion remains independently `completed`.
- Protocol JSON contains no named-project or domain literal.
- Protocol tests import no project runtime.
- Guard authority remains exact-path only.
- No shared runtime, Adapter, Role Pack, sibling-project edit, production integration, or new authority exists.

## Delivery Boundary

This plan delivers Stage P1 only. It does not authorize Stage P2 adapters, a second-consumer pilot, or runtime extraction. P2 requires a new plan, refreshed commit identities for all three projects, and explicit project-specific approval.

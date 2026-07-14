# Researcher and Research Critic Discovery Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a governed, event-triggered discovery layer in which a Researcher proposes new strategy families, an independent Research Critic challenges them, a human selects at most one direction, and the existing Research Director alone converts the approved direction into an unexecuted formal proposal.

**Architecture:** Agentic workers are provider-neutral and produce schema-bound JSON from checked-in prompt packets; the repository never calls a model API or reads a model credential. Deterministic Python owns source validation, fixed-scope enforcement, ranking, immutable fingerprints, state transitions, human approval binding, registry writes, audit output, and Research Director handoff. The first acceptance run stops before Candidate creation or Campaign execution.

**Tech Stack:** Python 3.12 from `.venv-freqtrade/Scripts/python.exe`, standard library, `jsonschema` 4.26.0, SQLite Director Registry, repository simple-YAML loader, `unittest`, PowerShell readiness checks, Node.js guard scripts.

## Global Constraints

- Run Python only with `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe`; do not use `python`, `py`, or PATH discovery.
- Do not install or update dependencies. The approved runtime and lock files remain unchanged.
- Do not add an OpenAI, Anthropic, or other model-provider SDK. Agent workers operate outside the deterministic control plane and submit JSON through inbox directories.
- Keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, primary `1h`, informative `4h`, existing runtime, and existing risk parameters fixed.
- Do not access Validation results, Holdout, private APIs, secrets, live accounts, or unapproved new datasets.
- Researcher and Critic may not create a Candidate, modify strategy/risk code, run backtests, compile Campaigns, or authorize execution.
- Human-facing Markdown and decision explanations are Simplified Chinese. Machine-facing filenames, JSON keys, enums, schemas, and registry columns are English.
- Each discovery cycle produces 6-10 immutable idea versions, no more than two per strategy family, and a shortlist of 0-3 ideas.
- A human may select at most one idea per cycle. Direction approval never sets `execution_authorized` to true.
- Use exact-path staging for every commit. Never use `git add -A`, `git add .`, or broad globs.
- Preserve existing baseline debt; new failures are regressions, while recorded baseline failures remain visible.

---

## File Structure

### New contract and policy files

- `research/discovery/schemas/research-trigger.schema.json`: trigger contract and allowed event types.
- `research/discovery/schemas/research-idea.schema.json`: Researcher output contract.
- `research/discovery/schemas/research-critique.schema.json`: Critic output contract and normalized ranking inputs.
- `research/discovery/schemas/research-shortlist.schema.json`: deterministic 0-3 ranking result.
- `research/discovery/schemas/research-direction-approval.schema.json`: human direction decision and bound fingerprints.
- `research/discovery/schemas/research-direction-handoff.schema.json`: non-executing Director handoff.
- `research/discovery/policy/source-policy.yaml`: source classes, required metadata, and forbidden inputs.
- `research/discovery/policy/ranking-policy.yaml`: weights, penalties, threshold, and tie-break order.

### New prompt and implementation files

- `research/discovery/prompts/researcher.md`: provider-neutral Researcher task contract.
- `research/discovery/prompts/critic.md`: independent adversarial review contract.
- `scripts/research_discovery_common.py`: schema validation, fingerprints, fixed-scope checks, source gates, state transitions, and ranking.
- `scripts/research_discovery_trigger.py`: trigger creation, idempotent run preparation, temporary inbox allocation, and Researcher packet rendering.
- `scripts/research_discovery_review.py`: idea/critique inbox ingestion, revision limits, deterministic shortlist, and Chinese review packet.
- `scripts/research_discovery_route.py`: human decision validation and non-executing handoff generation.

### Existing files to modify

- `scripts/research_director_common.py:15,146-303,305-383`: schema version 5, append-only discovery tables, summary/export coverage.
- `scripts/export_director_registry.py:12-28`: include discovery tables.
- `scripts/build_current_research_state.py:457-482`: attach discovery history to future state snapshots.
- `scripts/research_director.py:61-121,311-350`: convert one valid discovery handoff into `research-proposal-v1` without execution authority.
- `scripts/guard_harness_diff.js:100-125,340-405`: add exact discovery implementation paths and narrowly bounded generated-artifact prefixes.

### New tests and fixtures

- `tests/test_research_discovery_contracts.py`: schema, policy, source, scope, fingerprint, and score tests.
- `tests/test_research_discovery_registry.py`: migration, idempotency, export, and state-summary tests.
- `tests/test_research_discovery_workflow.py`: trigger, inbox, Critic, shortlist, approval, handoff, Director conversion, and dry-run invariants.
- `tests/fixtures/research-discovery/ideas/`: six deterministic multi-family idea fixtures.
- `tests/fixtures/research-discovery/critiques/`: matching independent Critic fixtures.
- `tests/fixtures/research-discovery/human-direction-approved-rank-1.json`: fingerprint-free decision request used only to exercise binding code in temporary directories.

---

### Task 1: Freeze Discovery Schemas and Policies

**Files:**
- Create: `research/discovery/schemas/research-trigger.schema.json`
- Create: `research/discovery/schemas/research-idea.schema.json`
- Create: `research/discovery/schemas/research-critique.schema.json`
- Create: `research/discovery/schemas/research-shortlist.schema.json`
- Create: `research/discovery/schemas/research-direction-approval.schema.json`
- Create: `research/discovery/schemas/research-direction-handoff.schema.json`
- Create: `research/discovery/policy/source-policy.yaml`
- Create: `research/discovery/policy/ranking-policy.yaml`
- Create: `tests/test_research_discovery_contracts.py`

**Interfaces:**
- Consumes: design contract in `docs/superpowers/specs/2026-07-14-researcher-critic-discovery-design.md`.
- Produces: six Draft 2020-12 schemas; source policy version `research-source-policy-v1`; ranking policy version `research-ranking-policy-v1`.

- [ ] **Step 1: Write the failing schema and policy test**

Create `tests/test_research_discovery_contracts.py` with the imports, paths, and first contract test:

```python
import copy
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document  # noqa: E402


SCHEMAS = {
    "research-trigger.schema.json": "research-trigger-v1",
    "research-idea.schema.json": "research-idea-v1",
    "research-critique.schema.json": "research-critique-v1",
    "research-shortlist.schema.json": "research-shortlist-v1",
    "research-direction-approval.schema.json": "research-direction-approval-v1",
    "research-direction-handoff.schema.json": "research-direction-handoff-v1",
}


class ResearchDiscoveryContractTests(unittest.TestCase):
    def test_schemas_are_valid_draft_2020_12_and_pin_schema_version(self):
        root = ROOT / "research/discovery/schemas"
        for filename, version in SCHEMAS.items():
            schema = load_document(root / filename)
            jsonschema.Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["properties"]["schema_version"]["const"], version)
            self.assertFalse(schema["additionalProperties"])

    def test_source_and_ranking_policy_are_frozen(self):
        source = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        ranking = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        self.assertEqual(source["schema_version"], "research-source-policy-v1")
        self.assertEqual(set(source["classes"]), {"A", "B", "C"})
        self.assertEqual(ranking["schema_version"], "research-ranking-policy-v1")
        self.assertEqual(sum(ranking["weights"].values()), 1.0)
        self.assertEqual(ranking["shortlist_threshold"], 0.55)
        self.assertEqual(ranking["max_shortlist"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_contracts -v
```

Expected: FAIL with `FileNotFoundError` for `research/discovery/schemas/research-trigger.schema.json`.

- [ ] **Step 3: Create the source and ranking policies**

Write `research/discovery/policy/source-policy.yaml` exactly as:

```yaml
schema_version: "research-source-policy-v1"
classes:
  A: ["repository_frozen_data", "completed_research_artifact", "research_registry", "branch_closure", "approved_governance", "official_exchange_documentation"]
  B: ["peer_reviewed_paper", "reputable_preprint", "textbook", "institutional_research_report"]
  C: ["public_strategy_repository", "blog", "forum", "social_media", "video", "ranking", "commercial_claim"]
pass_requirement: "at_least_one_A_or_B"
class_c_only_result: "reject"
external_required_fields: ["canonical_url", "source_class", "publisher_type", "retrieved_at", "claim", "content_fingerprint", "staleness_assessment", "licensing_constraints"]
forbidden_inputs: ["validation_result", "holdout", "private_api", "secret", "live_account", "unapproved_dataset"]
store_full_copyrighted_source: false
```

Write `research/discovery/policy/ranking-policy.yaml` exactly as:

```yaml
schema_version: "research-ranking-policy-v1"
weights: {"expected_information_gain": 0.30, "falsifiability_and_mechanism_clarity": 0.20, "feasibility_with_existing_data": 0.20, "novelty_and_non_duplication": 0.15, "robustness_relevance": 0.15}
penalties:
  risk: {"low": 0.00, "medium": 0.05, "high": 0.15, "forbidden": "reject"}
  cost: {"low": 0.00, "medium": 0.03, "high": 0.08}
  contamination: {"none": 0.00, "low": 0.02, "medium": 0.08, "high": "reject"}
  sources: {"includes_A": 0.00, "B_without_A": 0.02, "C_only": "reject"}
shortlist_threshold: 0.55
max_shortlist: 3
initial_idea_min: 6
initial_idea_max: 10
max_ideas_per_family: 2
max_revisions_per_cycle: 1
tie_breakers: ["lower_risk", "lower_cost", "semantic_fingerprint"]
return_metrics_are_ranking_inputs: false
```

- [ ] **Step 4: Create the six strict JSON schemas**

Use this common envelope in every schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [],
  "properties": {},
  "additionalProperties": false
}
```

Populate each file with these exact required keys and constrained properties:

```python
SCHEMA_FIELDS = {
    "research-trigger.schema.json": {
        "required": ["schema_version", "trigger_id", "event_type", "event_ref", "research_state_fingerprint", "constitution_fingerprint", "source_policy_version", "created_at", "trigger_fingerprint"],
        "const": "research-trigger-v1",
        "enums": {"event_type": ["campaign_completed", "branch_closed", "director_no_research", "manual_request"]},
        "fingerprints": ["research_state_fingerprint", "constitution_fingerprint", "trigger_fingerprint"],
    },
    "research-idea.schema.json": {
        "required": ["schema_version", "idea_id", "idea_version", "strategy_family", "title", "plain_language_summary_zh", "falsifiable_hypothesis", "proposed_market_mechanism", "supporting_evidence", "contradictory_evidence", "source_refs", "novelty_vs_existing_research", "required_datasets", "data_readiness", "fixed_scope_confirmation", "minimal_test_method", "comparison_baseline", "expected_information_gain", "estimated_cost", "risk_class", "contamination_risk", "falsification_conditions", "stop_conditions", "known_limitations", "research_state_fingerprint", "semantic_fingerprint"],
        "const": "research-idea-v1",
        "enums": {"risk_class": ["low", "medium", "high", "forbidden"], "contamination_risk": ["none", "low", "medium", "high"], "data_readiness": ["ready", "data_readiness_required", "out_of_v1_scope"]},
        "fingerprints": ["research_state_fingerprint", "semantic_fingerprint"],
    },
    "research-critique.schema.json": {
        "required": ["schema_version", "critique_id", "idea_id", "idea_semantic_fingerprint", "verdict", "source_verification", "duplicate_research_check", "falsifiability_assessment", "data_readiness_assessment", "leakage_and_overfit_risks", "transaction_cost_challenge", "strongest_counterevidence", "alternative_explanations", "fatal_objections", "score_adjustments", "ranking_inputs", "critic_fingerprint"],
        "const": "research-critique-v1",
        "enums": {"verdict": ["pass", "revise", "reject"]},
        "fingerprints": ["idea_semantic_fingerprint", "critic_fingerprint"],
    },
    "research-shortlist.schema.json": {
        "required": ["schema_version", "discovery_run_id", "eligible_idea_count", "ranking_policy_version", "ranked_ideas", "recommended_idea_id", "recommendation", "recommendation_reason_zh", "research_state_fingerprint", "shortlist_fingerprint"],
        "const": "research-shortlist-v1",
        "enums": {"recommendation": ["research_recommended", "no_research_recommended"]},
        "fingerprints": ["research_state_fingerprint", "shortlist_fingerprint"],
    },
    "research-direction-approval.schema.json": {
        "required": ["schema_version", "discovery_run_id", "decision", "selected_idea_id", "selected_idea_fingerprint", "selected_critique_fingerprint", "shortlist_fingerprint", "research_state_fingerprint", "constitution_fingerprint", "reviewer_type", "decision_reason_zh", "decided_at", "approval_fingerprint"],
        "const": "research-direction-approval-v1",
        "enums": {"decision": ["approved_for_director_handoff", "rejected", "deferred"], "reviewer_type": ["human_user"]},
        "fingerprints": ["shortlist_fingerprint", "research_state_fingerprint", "constitution_fingerprint", "approval_fingerprint"],
    },
    "research-direction-handoff.schema.json": {
        "required": ["schema_version", "discovery_run_id", "idea_ref", "critique_ref", "approval_ref", "idea_fingerprint", "critique_fingerprint", "approval_fingerprint", "shortlist_fingerprint", "research_state_fingerprint", "constitution_fingerprint", "research_question", "execution_authorized", "handoff_fingerprint"],
        "const": "research-direction-handoff-v1",
        "enums": {},
        "fingerprints": ["idea_fingerprint", "critique_fingerprint", "approval_fingerprint", "shortlist_fingerprint", "research_state_fingerprint", "constitution_fingerprint", "handoff_fingerprint"],
    },
}
```

For every required string key use `{"type": "string", "minLength": 1}`. Fingerprints additionally use `"pattern": "^[a-f0-9]{64}$"`. Use arrays with explicit item schemas; make `ranked_ideas` have `"maxItems": 3`; make `recommended_idea_id` and approval selection fields nullable; set handoff `execution_authorized` to `{"const": false}`. Define `ranking_inputs` as an object containing exactly the five ranking-policy weight keys, each a number from 0 to 1. Define `estimated_cost` as an object requiring `experiments`, `wall_clock_minutes`, and `compute_class` (`low`, `medium`, `high`). Define `fixed_scope_confirmation` as an object requiring the fixed exchange, market, margin, timeframe, Development-only, unchanged-risk, no-new-dataset, no-Validation, and no-Holdout declarations.

- [ ] **Step 5: Run the contract test green**

Run the Task 1 command again.

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 6: Commit the frozen contracts**

```powershell
git add -- research/discovery/schemas/research-trigger.schema.json research/discovery/schemas/research-idea.schema.json research/discovery/schemas/research-critique.schema.json research/discovery/schemas/research-shortlist.schema.json research/discovery/schemas/research-direction-approval.schema.json research/discovery/schemas/research-direction-handoff.schema.json research/discovery/policy/source-policy.yaml research/discovery/policy/ranking-policy.yaml tests/test_research_discovery_contracts.py
git commit -m "governance(discovery): freeze schemas and policies"
```

---

### Task 2: Implement Deterministic Validation, Scope Gates, Fingerprints, and Ranking

**Files:**
- Create: `scripts/research_discovery_common.py`
- Modify: `tests/test_research_discovery_contracts.py`

**Interfaces:**
- Consumes: `load_document`, `fingerprint`, `write_json` from `research_director_common.py`; schemas and policies from Task 1.
- Produces: `DiscoveryError`, `validate_artifact()`, `artifact_fingerprint()`, `assert_fixed_scope()`, `validate_sources()`, `score_idea()`, `rank_eligible()`, `validate_transition()`, `write_immutable_json()`.

- [ ] **Step 1: Add failing deterministic-core tests**

Append tests that import the new interfaces and assert these exact behaviors:

```python
from research_discovery_common import (  # noqa: E402
    DiscoveryError,
    artifact_fingerprint,
    assert_fixed_scope,
    rank_eligible,
    score_idea,
    validate_sources,
    validate_transition,
)

    def test_fixed_scope_rejects_validation_and_new_dataset(self):
        fixed = {
            "exchange": "binance",
            "market": "USD-M Futures",
            "margin_mode": "isolated",
            "primary_timeframe": "1h",
            "informative_timeframes": ["4h"],
            "development_only": True,
            "risk_parameters_unchanged": True,
            "new_dataset": False,
            "validation_access": False,
            "holdout_access": False,
        }
        assert_fixed_scope(fixed)
        invalid = copy.deepcopy(fixed)
        invalid["validation_access"] = True
        with self.assertRaisesRegex(DiscoveryError, "validation_forbidden"):
            assert_fixed_scope(invalid)

    def test_source_gate_requires_class_a_or_b(self):
        validate_sources([{"source_class": "A", "path": "research/director/current-research-state.json", "claim": "state"}], ROOT)
        with self.assertRaisesRegex(DiscoveryError, "class_c_only"):
            validate_sources([{"source_class": "C", "canonical_url": "https://example.invalid/post", "publisher_type": "blog", "retrieved_at": "2026-07-14T00:00:00Z", "claim": "idea", "content_fingerprint": "a" * 64, "staleness_assessment": "unknown", "licensing_constraints": "summary_only"}], ROOT)

    def test_ranking_is_deterministic_and_excludes_rejected_items(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        idea = {"idea_id": "trend-v1", "strategy_family": "trend_following", "risk_class": "low", "estimated_cost": {"compute_class": "low"}, "contamination_risk": "none", "semantic_fingerprint": "1" * 64}
        critique = {"verdict": "pass", "critic_fingerprint": "2" * 64, "source_verification": {"highest_class": "A"}, "ranking_inputs": {key: 0.8 for key in policy["weights"]}}
        self.assertEqual(score_idea(idea, critique, policy), 0.8)
        ranked = rank_eligible([(idea, critique), ({**idea, "idea_id": "rejected"}, {**critique, "verdict": "reject"})], policy)
        self.assertEqual([entry["idea_id"] for entry in ranked], ["trend-v1"])

    def test_state_machine_does_not_skip_human_approval(self):
        validate_transition("shortlisted", "human_approved")
        with self.assertRaisesRegex(DiscoveryError, "illegal_transition"):
            validate_transition("shortlisted", "handed_to_director")
```

- [ ] **Step 2: Run the new tests red**

Run the Task 1 test command.

Expected: FAIL with `ModuleNotFoundError: No module named 'research_discovery_common'`.

- [ ] **Step 3: Implement `scripts/research_discovery_common.py`**

Implement the full public surface with these signatures and rules:

```python
class DiscoveryError(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def artifact_fingerprint(payload: dict[str, object], fingerprint_field: str) -> str:
    excluded = {fingerprint_field, "created_at", "decided_at"}
    return fingerprint({key: value for key, value in payload.items() if key not in excluded})


def validate_artifact(repo: Path, schema_filename: str, payload: dict[str, object]) -> None:
    schema = load_document(repo / "research/discovery/schemas" / schema_filename)
    jsonschema.Draft202012Validator(schema).validate(payload)


def assert_fixed_scope(scope: dict[str, object]) -> None:
    expected = {
        "exchange": "binance",
        "market": "USD-M Futures",
        "margin_mode": "isolated",
        "primary_timeframe": "1h",
        "informative_timeframes": ["4h"],
        "development_only": True,
        "risk_parameters_unchanged": True,
        "new_dataset": False,
        "validation_access": False,
        "holdout_access": False,
    }
    for key, value in expected.items():
        if scope.get(key) != value:
            reason = "validation_forbidden" if key == "validation_access" else "fixed_scope_violation"
            raise DiscoveryError(reason, f"{key} must equal {value!r}")


def validate_sources(source_refs: list[dict[str, object]], repo: Path) -> str:
    classes = {str(item.get("source_class")) for item in source_refs}
    if not classes.intersection({"A", "B"}):
        raise DiscoveryError("class_c_only", "at least one Class A or B source is required")
    required_external = {"canonical_url", "publisher_type", "retrieved_at", "claim", "content_fingerprint", "staleness_assessment", "licensing_constraints"}
    for item in source_refs:
        source_class = str(item.get("source_class"))
        if source_class == "A" and item.get("path"):
            path = (repo / str(item["path"])).resolve()
            if not path.is_relative_to(repo.resolve()) or not path.is_file():
                raise DiscoveryError("source_missing", str(item["path"]))
        elif not required_external.issubset(item):
            raise DiscoveryError("external_source_metadata_incomplete", str(item.get("canonical_url")))
    return "includes_A" if "A" in classes else "B_without_A"


def score_idea(idea: dict[str, object], critique: dict[str, object], policy: dict[str, object]) -> float:
    if critique["verdict"] != "pass":
        raise DiscoveryError("critic_not_passed", str(idea["idea_id"]))
    ranking_inputs = critique["ranking_inputs"]
    base = sum(float(policy["weights"][key]) * float(ranking_inputs[key]) for key in policy["weights"])
    source_key = critique["source_verification"]["highest_class"]
    source_penalty_key = "includes_A" if source_key == "A" else "B_without_A" if source_key == "B" else "C_only"
    penalty_values = (
        policy["penalties"]["risk"][idea["risk_class"]],
        policy["penalties"]["cost"][idea["estimated_cost"]["compute_class"]],
        policy["penalties"]["contamination"][idea["contamination_risk"]],
        policy["penalties"]["sources"][source_penalty_key],
    )
    if "reject" in penalty_values:
        raise DiscoveryError("ranking_policy_reject", str(idea["idea_id"]))
    return round(base - sum(float(value) for value in penalty_values), 6)


def rank_eligible(items: list[tuple[dict[str, object], dict[str, object]]], policy: dict[str, object]) -> list[dict[str, object]]:
    risk_order = {"low": 0, "medium": 1, "high": 2, "forbidden": 3}
    cost_order = {"low": 0, "medium": 1, "high": 2}
    ranked = []
    for idea, critique in items:
        if critique["verdict"] != "pass":
            continue
        try:
            final_score = score_idea(idea, critique, policy)
        except DiscoveryError:
            continue
        if final_score >= float(policy["shortlist_threshold"]):
            ranked.append({"idea_id": idea["idea_id"], "idea_fingerprint": idea["semantic_fingerprint"], "critique_fingerprint": critique["critic_fingerprint"], "strategy_family": idea["strategy_family"], "risk_class": idea["risk_class"], "cost_class": idea["estimated_cost"]["compute_class"], "final_score": final_score})
    ranked.sort(key=lambda item: (-item["final_score"], risk_order[item["risk_class"]], cost_order[item["cost_class"]], item["idea_fingerprint"]))
    return ranked[: int(policy["max_shortlist"])]


TRANSITIONS = {
    "discovered": {"critic_rejected", "criticized", "revision_exhausted", "out_of_v1_scope", "insufficient_source_evidence", "data_readiness_required"},
    "criticized": {"shortlisted", "critic_rejected"},
    "shortlisted": {"human_approved", "rejected", "deferred", "no_research_recommended", "fingerprint_invalidated"},
    "human_approved": {"handed_to_director", "fingerprint_invalidated"},
    "handed_to_director": {"converted", "director_rejected"},
}


def validate_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise DiscoveryError("illegal_transition", f"{current} -> {target}")


def write_immutable_json(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        existing = load_document(path)
        if fingerprint(existing) != fingerprint(payload):
            raise DiscoveryError("immutable_artifact_conflict", path.as_posix())
        return
    write_json(path, payload)
```

Include imports for `jsonschema`, `Path`, `load_document`, `fingerprint`, and `write_json`.

- [ ] **Step 4: Run deterministic-core tests green**

Run the Task 1 test command.

Expected: all contract and deterministic-core tests pass.

- [ ] **Step 5: Commit the deterministic core**

```powershell
git add -- scripts/research_discovery_common.py tests/test_research_discovery_contracts.py
git commit -m "feat(discovery): add deterministic validation and ranking"
```

---

### Task 3: Extend the Director Registry and Current Research State

**Files:**
- Modify: `scripts/research_director_common.py:15,146-303,305-383`
- Modify: `scripts/export_director_registry.py:12-28`
- Modify: `scripts/build_current_research_state.py:457-482`
- Create: `tests/test_research_discovery_registry.py`

**Interfaces:**
- Consumes: discovery artifact fingerprints and run IDs.
- Produces: schema version 5 tables, `discovery_registry_summary()`, exported discovery rows, and `research_discovery` in future state snapshots.

- [ ] **Step 1: Write failing registry migration and idempotency tests**

Create `tests/test_research_discovery_registry.py` with tests that open a temporary Director Registry and assert the seven tables below, schema version 5, unique trigger fingerprints, and exported empty rows. Add a test that inserts one completed discovery run and asserts `build_state(...)["research_discovery"]["completed_runs"] == 1`.

Use this table set in the test:

```python
DISCOVERY_TABLES = {
    "research_discovery_runs",
    "research_discovery_ideas",
    "research_discovery_critiques",
    "research_discovery_shortlists",
    "research_discovery_approvals",
    "research_discovery_handoffs",
    "research_discovery_events",
}
```

- [ ] **Step 2: Run registry tests red**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_registry -v
```

Expected: FAIL because the discovery tables and state summary do not exist.

- [ ] **Step 3: Add schema version 5 tables**

Set `DIRECTOR_SCHEMA_VERSION = 5` and append these exact table contracts to `ensure_director_schema()`:

```sql
CREATE TABLE IF NOT EXISTS research_discovery_runs (
  run_id TEXT PRIMARY KEY,
  trigger_fingerprint TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  state_fingerprint TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_ideas (
  idea_key TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  idea_id TEXT NOT NULL,
  idea_version INTEGER NOT NULL,
  semantic_fingerprint TEXT NOT NULL UNIQUE,
  strategy_family TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_critiques (
  critique_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  idea_key TEXT NOT NULL,
  verdict TEXT NOT NULL,
  critic_fingerprint TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_shortlists (
  run_id TEXT PRIMARY KEY,
  shortlist_fingerprint TEXT NOT NULL UNIQUE,
  recommendation TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_approvals (
  approval_fingerprint TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  selected_idea_id TEXT,
  payload_json TEXT NOT NULL,
  decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_handoffs (
  handoff_fingerprint TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  idea_id TEXT NOT NULL,
  status TEXT NOT NULL,
  director_result_code TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_discovery_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  reason_code TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

- [ ] **Step 4: Export and summarize discovery history**

Add all seven table names to `export_director_registry.TABLES` and `director_registry_export()`.

Add this public helper to `research_director_common.py`:

```python
def discovery_registry_summary(path: str | Path | None) -> dict[str, Any]:
    if not path or not Path(path).is_file():
        return {"available": False, "completed_runs": 0, "director_rejections": 0, "recent_ideas": []}
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "research_discovery_runs" not in tables:
        connection.close()
        return {"available": True, "completed_runs": 0, "director_rejections": 0, "recent_ideas": []}
    completed = connection.execute("SELECT COUNT(*) FROM research_discovery_runs WHERE status IN ('completed', 'no_research_recommended')").fetchone()[0]
    rejected = connection.execute("SELECT COUNT(*) FROM research_discovery_handoffs WHERE status='director_rejected'").fetchone()[0]
    ideas = [dict(row) for row in connection.execute("SELECT idea_id, idea_version, strategy_family, status, semantic_fingerprint FROM research_discovery_ideas ORDER BY created_at DESC, idea_key LIMIT 20")]
    connection.close()
    return {"available": True, "completed_runs": completed, "director_rejections": rejected, "recent_ideas": ideas}
```

Change the signature to `build_state(repo: Path, source_registry: Path | None = None, data_lineage: Path | None = None, director_registry: Path | None = None) -> dict[str, Any]`. Add `state["research_discovery"] = discovery_registry_summary(director_registry)` before the final state fingerprint is calculated, preserve the first three positional arguments for existing callers, and pass `Path(args.director_registry)` from `main()` only when the CLI value is present.

- [ ] **Step 5: Run registry tests green and existing Director tests**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_registry tests.test_stage4a_research_director -v
```

Expected: PASS; existing Director behavior remains unchanged.

- [ ] **Step 6: Commit the registry migration**

```powershell
git add -- scripts/research_director_common.py scripts/export_director_registry.py scripts/build_current_research_state.py tests/test_research_discovery_registry.py
git commit -m "feat(discovery): register append-only discovery history"
```

---

### Task 4: Prepare Idempotent Trigger Runs and Agent Packets

**Files:**
- Create: `research/discovery/prompts/researcher.md`
- Create: `research/discovery/prompts/critic.md`
- Create: `scripts/research_discovery_trigger.py`
- Create: `tests/test_research_discovery_workflow.py`

**Interfaces:**
- Consumes: current state, approved Constitution, source policy, one allowed event, Director Registry.
- Produces: `create_trigger() -> dict`, `render_researcher_packet(repo: Path, run_path: Path, trigger: dict[str, object], temp_inbox: Path) -> str`, `prepare_run() -> dict`, immutable `trigger.json`, Chinese/English Researcher task packet, and an idempotent registry run.

- [ ] **Step 1: Write failing trigger and idempotency tests**

Create `tests/test_research_discovery_workflow.py`. Use a temporary repository copy containing only required contracts, a temporary Registry, and a fixed state/Constitution. Assert:

```python
trigger = create_trigger(
    event_type="manual_request",
    event_ref="human-request-2026-07-14",
    state=state,
    constitution=constitution,
    source_policy=source_policy,
    created_at="2026-07-14T00:00:00+00:00",
)
self.assertEqual(trigger["schema_version"], "research-trigger-v1")
self.assertEqual(len(trigger["trigger_fingerprint"]), 64)
first = prepare_run(repo, trigger, registry)
second = prepare_run(repo, trigger, registry)
self.assertEqual(first["run_id"], second["run_id"])
self.assertTrue((repo / first["run_path"] / "trigger.json").is_file())
self.assertTrue((repo / first["run_path"] / "researcher-task.md").is_file())
```

Also assert that `event_type="timer"` fails with `unsupported_trigger`, and state conflicts fail with `state_conflict`.

- [ ] **Step 2: Run trigger tests red**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_workflow -v
```

Expected: FAIL because `research_discovery_trigger.py` does not exist.

- [ ] **Step 3: Write the Researcher prompt contract**

Create `research/discovery/prompts/researcher.md` with these operative rules:

```markdown
# Researcher Role Contract

Generate 6-10 distinct `research-idea-v1` JSON objects. Use at most two ideas per `strategy_family`. You may propose entirely different strategy families, but every idea must keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, `1h` primary, `4h` informative, the approved runtime, and existing risk parameters fixed.

Read only sources listed in the task packet. Do not read Validation results, Holdout, secrets, private APIs, live accounts, strategy mutation paths, Candidate paths, or execution runners. External sources may inform an idea only when their required provenance metadata are included. Do not download a market dataset.

Each hypothesis must be falsifiable. Include supporting evidence, contradictory evidence, the strongest known limitation, the smallest useful test, comparison baseline, estimated experiment count, wall-clock minutes, compute class, stop conditions, and a semantic fingerprint request. Do not promise return, win rate, or profitability. Write JSON to the provided inbox only; do not modify governed run artifacts.
```

Create `research/discovery/prompts/critic.md` with these rules:

```markdown
# Research Critic Role Contract

Review each immutable `research-idea-v1` independently and emit one `research-critique-v1` JSON object per idea. Do not edit, replace, or silently improve the Researcher artifact.

Verify source provenance, duplication, falsifiability, data readiness, fixed scope, leakage, overfitting, transaction-cost sensitivity, alternative explanations, strongest counterevidence, and fatal objections. Set `verdict` to `pass`, `revise`, or `reject`. Supply all five normalized `ranking_inputs` from 0 to 1 with written justification in the assessment fields. A Class C-only idea cannot pass. A missing dataset becomes `data_readiness_required`, not an executable strategy study.

Write JSON to the provided Critic inbox only. Do not create a Candidate, run an experiment, modify a strategy, access Validation/Holdout, or authorize execution.
```

- [ ] **Step 4: Implement trigger creation and run preparation**

In `scripts/research_discovery_trigger.py`, implement:

Import `argparse`, `json`, `tempfile`, and `Path`, plus the required helpers from `research_director_common` and `research_discovery_common`.

```python
ALLOWED_EVENTS = {"campaign_completed", "branch_closed", "director_no_research", "manual_request"}


def create_trigger(event_type: str, event_ref: str, state: dict[str, object], constitution: dict[str, object], source_policy: dict[str, object], created_at: str | None = None) -> dict[str, object]:
    if event_type not in ALLOWED_EVENTS:
        raise DiscoveryError("unsupported_trigger", event_type)
    if state.get("state_conflicts"):
        raise DiscoveryError("state_conflict", "current research state contains conflicts")
    trigger = {
        "schema_version": "research-trigger-v1",
        "trigger_id": f"discovery-trigger-{fingerprint({'event_type': event_type, 'event_ref': event_ref, 'state': state['state_fingerprint']})[:16]}",
        "event_type": event_type,
        "event_ref": event_ref,
        "research_state_fingerprint": state["state_fingerprint"],
        "constitution_fingerprint": fingerprint(constitution),
        "source_policy_version": source_policy["schema_version"],
        "created_at": created_at or utc_now(),
    }
    trigger["trigger_fingerprint"] = artifact_fingerprint(trigger, "trigger_fingerprint")
    return trigger


def prepare_run(repo: Path, trigger: dict[str, object], registry_path: Path) -> dict[str, object]:
    validate_artifact(repo, "research-trigger.schema.json", trigger)
    connection = open_director_registry(registry_path)
    existing = connection.execute("SELECT run_id, payload_json FROM research_discovery_runs WHERE trigger_fingerprint=?", (trigger["trigger_fingerprint"],)).fetchone()
    if existing:
        connection.close()
        return json.loads(existing["payload_json"])
    run_id = f"discovery-run-{trigger['trigger_fingerprint'][:16]}"
    run_path = Path("research/discovery/runs") / run_id
    temp_inbox = Path(tempfile.gettempdir()) / "freqtrade-research-discovery" / run_id / "researcher"
    temp_inbox.mkdir(parents=True, exist_ok=True)
    result = {"run_id": run_id, "run_path": run_path.as_posix(), "researcher_inbox": str(temp_inbox), "status": "awaiting_researcher", "trigger_fingerprint": trigger["trigger_fingerprint"]}
    write_immutable_json(repo / run_path / "trigger.json", trigger)
    render_researcher_packet(repo, run_path, trigger, temp_inbox)
    connection.execute("INSERT INTO research_discovery_runs(run_id, trigger_fingerprint, status, state_fingerprint, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (run_id, trigger["trigger_fingerprint"], result["status"], trigger["research_state_fingerprint"], json.dumps(result, sort_keys=True), trigger["created_at"]))
    connection.commit()
    connection.close()
    return result
```

`render_researcher_packet()` must include the Researcher prompt, exact allowed source paths from current state, an absolute inbox under `$env:TEMP\freqtrade-research-discovery\<run-id>\researcher`, fixed scope, schema path, and forbidden paths. The temporary inbox is outside the repository; only validated artifacts are copied immutably into the run directory.

- [ ] **Step 5: Add the CLI and run tests green**

Expose `--event-type`, `--event-ref`, `--state`, `--constitution`, `--source-policy`, `--director-registry`, and `--repo-root`. The CLI prints only `run_id`, `run_path`, `status`, and `trigger_fingerprint`.

Run the Task 4 test command.

Expected: trigger, unsupported event, state-conflict, and idempotency tests pass.

- [ ] **Step 6: Commit trigger preparation**

```powershell
git add -- research/discovery/prompts/researcher.md research/discovery/prompts/critic.md scripts/research_discovery_trigger.py tests/test_research_discovery_workflow.py
git commit -m "feat(discovery): prepare idempotent agent runs"
```

---

### Task 5: Ingest Researcher and Critic Artifacts and Build the Top 3

**Files:**
- Create: `scripts/research_discovery_review.py`
- Create: `tests/fixtures/research-discovery/ideas/trend-following-v1.json`
- Create: `tests/fixtures/research-discovery/ideas/mean-reversion-v1.json`
- Create: `tests/fixtures/research-discovery/ideas/breakout-v1.json`
- Create: `tests/fixtures/research-discovery/ideas/volatility-v1.json`
- Create: `tests/fixtures/research-discovery/ideas/regime-switching-v1.json`
- Create: `tests/fixtures/research-discovery/ideas/market-structure-v1.json`
- Create: six matching files under `tests/fixtures/research-discovery/critiques/`
- Modify: `tests/test_research_discovery_workflow.py`

**Interfaces:**
- Consumes: validated trigger run, Researcher inbox, Critic inbox, schemas, policies, registry.
- Produces: `ingest_ideas()`, `render_critic_packet()`, `ingest_critiques()`, `build_shortlist()`, `render_human_review_zh()`.

- [ ] **Step 1: Add failing workflow tests for idea limits and Critic independence**

Add tests that assert:

```python
ideas = ingest_ideas(repo, run_id, ideas_inbox, registry)
self.assertEqual(len(ideas), 6)
self.assertEqual(max(Counter(item["strategy_family"] for item in ideas).values()), 1)
critic_packet = render_critic_packet(repo, run_id)
self.assertIn("Do not edit", critic_packet)
critiques = ingest_critiques(repo, run_id, critiques_inbox, registry)
self.assertEqual({item["idea_id"] for item in critiques}, {item["idea_id"] for item in ideas})
shortlist = build_shortlist(repo, run_id, registry)
self.assertLessEqual(len(shortlist["ranked_ideas"]), 3)
self.assertFalse("profit" in shortlist["recommendation_reason_zh"].lower())
```

Add negative cases for 5 ideas, 11 ideas, 3 ideas in one family, modified idea fingerprints, Class C-only sources, a missing critique, a second revision, `verdict=reject`, and all scores below 0.55.

- [ ] **Step 2: Run workflow tests red**

Run the Task 4 test command.

Expected: FAIL because review ingestion and fixtures do not exist.

- [ ] **Step 3: Create six valid multi-family fixtures and matching critiques**

Each idea fixture draft must use a distinct family, cite at least one real Class A repository path, bind the fixed scope exactly, and set `idea_version: 1`. The inbox draft omits `semantic_fingerprint`; deterministic ingestion adds the computed value and then validates the stored artifact against `research-idea-v1`.

Each Critic fixture draft must bind the computed idea fingerprint, use `verdict: pass` for at least three items, include explicit counterevidence, and provide all five numeric `ranking_inputs`. The draft omits `critic_fingerprint`; deterministic ingestion computes it before schema validation. Include one fixture below threshold to prove exclusion.

- [ ] **Step 4: Implement immutable inbox ingestion**

Implement these checks in `ingest_ideas()`:

```python
def ingest_ideas(repo: Path, run_id: str, inbox: Path, registry_path: Path) -> list[dict[str, object]]:
    payloads = [load_document(path) for path in sorted(inbox.glob("*.json"))]
    policy = load_document(repo / "research/discovery/policy/ranking-policy.yaml")
    if not int(policy["initial_idea_min"]) <= len(payloads) <= int(policy["initial_idea_max"]):
        raise DiscoveryError("idea_count_out_of_bounds", str(len(payloads)))
    family_counts = Counter(str(item["strategy_family"]) for item in payloads)
    if max(family_counts.values(), default=0) > int(policy["max_ideas_per_family"]):
        raise DiscoveryError("strategy_family_cap_exceeded", json.dumps(family_counts, sort_keys=True))
    stored = []
    for payload in payloads:
        payload.pop("semantic_fingerprint", None)
        assert_fixed_scope(payload["fixed_scope_confirmation"])
        validate_sources(payload["source_refs"], repo)
        payload["semantic_fingerprint"] = artifact_fingerprint(payload, "semantic_fingerprint")
        validate_artifact(repo, "research-idea.schema.json", payload)
        destination = repo / "research/discovery/runs" / run_id / "ideas" / f"{payload['idea_id']}-v{payload['idea_version']}.json"
        write_immutable_json(destination, payload)
        stored.append(payload)
    _record_ideas(registry_path, run_id, stored)
    return stored
```

Define the same-file private registry writer used above:

```python
def _record_ideas(registry_path: Path, run_id: str, ideas: list[dict[str, object]]) -> None:
    connection = open_director_registry(registry_path)
    for idea in ideas:
        idea_key = f"{run_id}:{idea['idea_id']}:v{idea['idea_version']}"
        connection.execute(
            "INSERT INTO research_discovery_ideas(idea_key, run_id, idea_id, idea_version, semantic_fingerprint, strategy_family, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (idea_key, run_id, idea["idea_id"], idea["idea_version"], idea["semantic_fingerprint"], idea["strategy_family"], "discovered", json.dumps(idea, sort_keys=True), utc_now()),
        )
    connection.commit()
    connection.close()
```

Implement `ingest_critiques()` with the same schema/fingerprint binding. It must compare the idea file hash before and after Critic ingestion, reject missing or extra idea IDs, and enforce one revision per run using registry idea versions.

- [ ] **Step 5: Implement deterministic shortlist and Chinese review packet**

`build_shortlist()` loads each latest idea and matching critique, calls `rank_eligible()`, emits zero to three entries, and computes `shortlist_fingerprint`. With no eligible item it sets `recommended_idea_id: null`, `recommendation: no_research_recommended`, and records a normal completed state.

`render_human_review_zh()` must render, for each ranked idea: study question, why now, mechanism, strongest objection, data readiness, minimal test, experiment/time/compute cost, stop condition, Critic verdict, score, and uncertainty. End with: `批准研究方向不代表盈利判断，也不授权创建 Candidate 或执行 Campaign。`

- [ ] **Step 6: Run workflow tests green**

Run the Task 4 test command.

Expected: all positive and fail-closed workflow tests pass.

- [ ] **Step 7: Commit review and shortlist support**

```powershell
git add -- scripts/research_discovery_review.py tests/test_research_discovery_workflow.py tests/fixtures/research-discovery/ideas tests/fixtures/research-discovery/critiques
git commit -m "feat(discovery): critique and rank research ideas"
```

---

### Task 6: Bind Human Direction Decisions and Create a Non-executing Handoff

**Files:**
- Create: `scripts/research_discovery_route.py`
- Create: `tests/fixtures/research-discovery/human-direction-approved-rank-1.json`
- Modify: `tests/test_research_discovery_workflow.py`

**Interfaces:**
- Consumes: shortlist, selected idea, selected critique, current state, approved Constitution, human decision request.
- Produces: `record_direction_decision() -> dict`, `create_handoff() -> dict`, immutable `approval.json`, immutable `handoff.json`, registry events.

- [ ] **Step 1: Add failing approval and fingerprint-binding tests**

Test these cases:

```python
approval = record_direction_decision(repo, run_id, {"decision": "approved_for_director_handoff", "selected_rank": 1, "reviewer_type": "human_user", "decision_reason_zh": "批准排名第一方向进入正式准备"}, state, constitution, registry, decided_at="2026-07-14T00:10:00+00:00")
self.assertEqual(approval["decision"], "approved_for_director_handoff")
handoff = create_handoff(repo, run_id, state, constitution, registry)
self.assertFalse(handoff["execution_authorized"])
self.assertEqual(handoff["idea_fingerprint"], approval["selected_idea_fingerprint"])
```

Add failures for non-human reviewer, selecting rank 4, selecting more than one idea, changed shortlist fingerprint, changed state fingerprint, changed Constitution fingerprint, changed idea/critique, rejected/deferred handoff, and a second conflicting approval.

- [ ] **Step 2: Run approval tests red**

Run the Task 4 test command.

Expected: FAIL because route functions do not exist.

- [ ] **Step 3: Implement human decision binding**

`record_direction_decision()` must load the immutable shortlist and resolve `selected_rank` to exactly one entry. It constructs all governed fields itself; the human request cannot supply fingerprints. For `rejected` or `deferred`, selection fields are null. For approval, all selection fingerprints are required and copied from governed artifacts.

Use:

```python
approval = {
    "schema_version": "research-direction-approval-v1",
    "discovery_run_id": run_id,
    "decision": request["decision"],
    "selected_idea_id": selected["idea_id"] if selected else None,
    "selected_idea_fingerprint": selected["idea_fingerprint"] if selected else None,
    "selected_critique_fingerprint": selected["critique_fingerprint"] if selected else None,
    "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
    "research_state_fingerprint": state["state_fingerprint"],
    "constitution_fingerprint": fingerprint(constitution),
    "reviewer_type": "human_user",
    "decision_reason_zh": request["decision_reason_zh"],
    "decided_at": decided_at or utc_now(),
}
approval["approval_fingerprint"] = artifact_fingerprint(approval, "approval_fingerprint")
```

Validate the schema before writing and insert the approval plus a `human_direction_decision` event in one SQLite transaction.

- [ ] **Step 4: Implement the non-executing handoff**

`create_handoff()` rechecks all bound fingerprints against current files, current state, and current Constitution. It writes:

```python
handoff = {
    "schema_version": "research-direction-handoff-v1",
    "discovery_run_id": run_id,
    "idea_ref": idea_path.relative_to(repo).as_posix(),
    "critique_ref": critique_path.relative_to(repo).as_posix(),
    "approval_ref": approval_path.relative_to(repo).as_posix(),
    "idea_fingerprint": idea["semantic_fingerprint"],
    "critique_fingerprint": critique["critic_fingerprint"],
    "approval_fingerprint": approval["approval_fingerprint"],
    "shortlist_fingerprint": approval["shortlist_fingerprint"],
    "research_state_fingerprint": state["state_fingerprint"],
    "constitution_fingerprint": fingerprint(constitution),
    "research_question": idea["falsifiable_hypothesis"],
    "execution_authorized": False,
}
handoff["handoff_fingerprint"] = artifact_fingerprint(handoff, "handoff_fingerprint")
```

- [ ] **Step 5: Run route tests green**

Run the Task 4 test command.

Expected: approval and handoff pass; every mismatch fails closed with a stable reason code.

- [ ] **Step 6: Commit approval and handoff routing**

```powershell
git add -- scripts/research_discovery_route.py tests/test_research_discovery_workflow.py tests/fixtures/research-discovery/human-direction-approved-rank-1.json
git commit -m "feat(discovery): bind human direction approval"
```

---

### Task 7: Let the Existing Research Director Convert a Valid Handoff

**Files:**
- Modify: `scripts/research_director.py:61-121,311-350`
- Modify: `tests/test_stage4a_research_director.py`
- Modify: `tests/test_research_discovery_workflow.py`

**Interfaces:**
- Consumes: one schema-valid, fingerprint-valid `research-direction-handoff-v1` plus its immutable idea, critique, approval, current state, and Constitution.
- Produces: `proposal_from_discovery_handoff(repo, handoff, state, constitution) -> dict[str, Any]`; existing `research-proposal-v1`; Director run with `execution_authorized: false`.

- [ ] **Step 1: Write failing Director conversion tests**

Add a test that uses the approved fixture run and asserts:

```python
proposal = proposal_from_discovery_handoff(ROOT, handoff, state, constitution)
jsonschema.Draft202012Validator(load_document(ROOT / "research/director/research-proposal.schema.json")).validate(proposal)
self.assertEqual(proposal["research_question"], idea["falsifiable_hypothesis"])
self.assertEqual(proposal["risk_class"], idea["risk_class"])
self.assertEqual(proposal["validation_requirement"], "none")
self.assertEqual(proposal["holdout_requirement"], "none")
self.assertFalse(proposal["execution_authorized"])
self.assertEqual(proposal["discovery_handoff_fingerprint"], handoff["handoff_fingerprint"])
```

Add failures for unapproved handoff, `execution_authorized: true`, stale state, stale Constitution, invalid approval fingerprint, closed-branch conflict, duplicate question fingerprint, missing dataset manifest, and forbidden risk.

- [ ] **Step 2: Run Director tests red**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_stage4a_research_director tests.test_research_discovery_workflow -v
```

Expected: FAIL because `proposal_from_discovery_handoff` is missing.

- [ ] **Step 3: Implement Director-owned conversion**

Add `proposal_from_discovery_handoff()` to `scripts/research_director.py`. It must:

1. Validate the handoff and all referenced artifacts.
2. Require a human `approved_for_director_handoff` record.
3. Require `execution_authorized is False`.
4. Re-run `branch_closure_check()`, duplicate question checks, required dataset manifest checks, and `route_proposal()`.
5. Build runtime and evaluation-policy references from the current state, not from Researcher claims.
6. Map `estimated_cost.experiments`, `estimated_cost.wall_clock_minutes`, and `estimated_cost.compute_class` into the proposal.
7. Add exact candidate/analysis/report paths only for a medium-risk new-family proposal; do not create those paths.
8. Set `approval_requirement` from `route_proposal()` and `execution_authorized: false`.
9. Attach `discovery_handoff_fingerprint`, `discovery_approval_fingerprint`, and `discovery_critique_fingerprint`.

Use `proposal_base()` for the existing proposal fields, then add the discovery fields and recompute `semantic_fingerprint`.

- [ ] **Step 4: Add a `--handoff` Director CLI path**

When `--handoff` is present, the CLI converts only that handoff and writes a Director run containing one unexecuted proposal or a machine-readable rejection. It must not call `compile_campaign.py`. Preserve the current generation path when `--handoff` is absent.

- [ ] **Step 5: Run Director and discovery tests green**

Run the Task 7 test command.

Expected: all existing Stage 4A tests and new handoff tests pass.

- [ ] **Step 6: Commit Director integration**

```powershell
git add -- scripts/research_director.py tests/test_stage4a_research_director.py tests/test_research_discovery_workflow.py
git commit -m "feat(director): accept governed discovery handoffs"
```

---

### Task 8: Add Exact Guards, Audit Reports, and an End-to-end Dry Run

**Files:**
- Modify: `scripts/guard_harness_diff.js:100-125,340-405`
- Modify: `scripts/research_discovery_review.py`
- Modify: `scripts/research_discovery_route.py`
- Modify: `tests/test_research_discovery_workflow.py`

**Interfaces:**
- Consumes: completed discovery run and optional Director conversion result.
- Produces: Chinese final Markdown, machine JSON audit, exact guard surface, and dry-run proof of zero execution side effects.

- [ ] **Step 1: Add failing guard and audit tests**

Add tests that parse `guard_harness_diff.js` and require exact entries for all schema, policy, prompt, script, and test files plus only these dynamic prefixes:

```text
research/discovery/runs/
reports/audits/research-discovery/
tests/fixtures/research-discovery/
```

Reject `research/**`, `reports/**`, `scripts/**`, `tests/**`, or any new broad staging rule. Add an end-to-end test that records the pre-run hashes of `strategies/`, `research/data/validation*`, and `research/data/holdout/`, then proves they are unchanged and that registry Campaign/Candidate counts do not increase.

- [ ] **Step 2: Run guard/audit tests red**

Run the Task 4 test command and:

```powershell
& 'C:\Program Files\nodejs\node.exe' scripts/guard_harness_diff.js
```

Expected: FAIL because discovery paths and final reports are not yet guarded.

- [ ] **Step 3: Add exact guard entries**

Add explicit `{ path: "..." }` entries for the six schemas, two policies, two prompts, four discovery scripts, three discovery test files, and the approved design/plan documents. Add only the three narrow prefixes listed in Step 1 for variable run and fixture artifacts. Do not add a repository inbox prefix; unvalidated agent output remains under the system temporary directory.

- [ ] **Step 4: Implement final audit rendering**

Add `build_final_audit(repo: Path, run_id: str, registry_path: Path, director_result: dict[str, object] | None = None) -> tuple[dict[str, object], str]` to `scripts/research_discovery_review.py`. The JSON must include:

```python
{
    "schema_version": "research-discovery-final-audit-v1",
    "run_id": run_id,
    "trigger_fingerprint": trigger["trigger_fingerprint"],
    "idea_count": len(ideas),
    "critique_count": len(critiques),
    "shortlist_count": len(shortlist["ranked_ideas"]),
    "recommendation": shortlist["recommendation"],
    "human_decision": approval["decision"] if approval else "pending_human_review",
    "handoff_created": handoff is not None,
    "director_result": director_result,
    "candidate_created": False,
    "campaign_started": False,
    "strategy_modified": False,
    "risk_modified": False,
    "validation_accesses": 0,
    "holdout_accesses": 0,
    "artifact_hashes": artifact_hashes,
    "registry_integrity": registry_integrity,
}
```

The Chinese Markdown must summarize the same fields without adding claims not present in JSON.

- [ ] **Step 5: Run focused tests and guards green**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_contracts tests.test_research_discovery_registry tests.test_research_discovery_workflow tests.test_stage4a_research_director -v
& 'C:\Program Files\nodejs\node.exe' --check scripts/guard_harness_diff.js
& 'C:\Program Files\nodejs\node.exe' scripts/guard_harness_diff.js
& 'C:\Program Files\nodejs\node.exe' scripts/guard_no_secret_material.js
```

Expected: all tests and guards pass; the dry run proves zero Candidate, Campaign, Validation, Holdout, strategy, and risk changes.

- [ ] **Step 6: Commit guards and audit support**

```powershell
git add -- scripts/guard_harness_diff.js scripts/research_discovery_review.py scripts/research_discovery_route.py tests/test_research_discovery_workflow.py
git commit -m "test(discovery): prove governed dry-run boundaries"
```

---

### Task 9: Run the Real Discovery Acceptance Cycle and Stop for Human Direction Review

**Files:**
- Create during execution: `research/discovery/runs/discovery-run-<fingerprint>/`
- Create during execution: `reports/audits/research-discovery/discovery-run-<fingerprint>-final-report.json`
- Create during execution: `reports/audits/research-discovery/discovery-run-<fingerprint>-final-report.md`
- Modify during execution: `research/director/registry-records.json`
- Modify during execution: `research/director/current-research-state.json`
- Modify during execution: `research/director/current-research-state.md`

**Interfaces:**
- Consumes: current clean state, current approved Constitution, real Researcher and Critic worker outputs, explicit human direction decision.
- Produces: real Top 3 or `no_research_recommended`, human decision, optional non-executing Director proposal, final audit, and updated exports. It produces no Candidate and starts no Campaign.

- [ ] **Step 1: Re-run the hard worktree gate**

```powershell
git status --short --branch
git rev-parse HEAD
git branch --show-current
```

Expected: the branch is the implementation branch selected at execution time and the versioned worktree is clean. Stop immediately if any tracked or untracked change exists.

- [ ] **Step 2: Create a manual-request trigger**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B scripts/research_discovery_trigger.py --event-type manual_request --event-ref human-approved-researcher-critic-v1 --state research/director/current-research-state.json --constitution research/governance/research-constitution.yaml --source-policy research/discovery/policy/source-policy.yaml --director-registry research/registry/stage4a-director.db --repo-root .
```

Expected: JSON containing one `run_id`, `status: awaiting_researcher`, and a 64-character trigger fingerprint.

- [ ] **Step 3: Execute the Researcher role through the checked-in packet**

Dispatch or run one agentic worker with only the generated `researcher-task.md` and allowed source list. Require 6-10 JSON files in that run's Researcher inbox. The worker must not modify any governed file.

Run the ingest CLI and expect `status: awaiting_critic`, `idea_count` from 6 through 10, `candidate_created: false`, and `campaign_started: false`.

- [ ] **Step 4: Execute the independent Critic role**

Use a fresh agentic worker or a fresh isolated context with only `critic-task.md`, immutable idea paths, and allowed evidence. Require one critique per latest idea version. Run the Critic ingest and shortlist CLI.

Expected: `shortlist_count` from 0 through 3. If zero, the run finishes with `no_research_recommended`; skip Steps 5-7 and proceed to verification.

- [ ] **Step 5: Stop and present the Chinese human review packet**

Do not record an approval until the user explicitly chooses one ranked direction, rejects all, or defers. The review packet must include Critic objections and must say that direction approval is not execution authorization.

- [ ] **Step 6: Record the explicit human decision**

If the user approves rank 1, run:

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B scripts/research_discovery_route.py approve --run-id <actual-run-id> --selected-rank 1 --reviewer-type human_user --reason-zh "批准排名第一方向进入 Research Director 正式准备，不授权 Candidate 或 Campaign" --state research/director/current-research-state.json --constitution research/governance/research-constitution.yaml --director-registry research/registry/stage4a-director.db
```

Replace `<actual-run-id>` only with the exact `run_id` emitted by Step 2. If the user rejects or defers, use the corresponding `reject` or `defer` subcommand and omit `--selected-rank`.

Expected: a fingerprint-bound approval. Only approval creates `handoff.json`; every result keeps `execution_authorized: false`.

- [ ] **Step 7: Let the Research Director convert the handoff without compiling**

For an approved handoff only:

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B scripts/research_director.py --state research/director/current-research-state.json --constitution research/governance/research-constitution.yaml --handoff research/discovery/runs/<actual-run-id>/handoff.json --output research/director/discovery-handoff/proposals/director-run.json --director-registry research/registry/stage4a-director.db
```

Expected: one formal proposal or a machine-readable Director rejection, `execution_authorized: false`, no compilation, no Candidate, and no Campaign.

- [ ] **Step 8: Run complete verification**

```powershell
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B -m unittest tests.test_research_discovery_contracts tests.test_research_discovery_registry tests.test_research_discovery_workflow tests.test_stage4a_research_director -v
& .\scripts\run_agent_readiness_checks.ps1
& 'D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe' -B scripts/verify_test_baseline.py --run --profile clean_worktree_portable
git diff -- strategies research/data/validation* research/data/holdout research/evaluation/evaluation-policy.yaml research/governance/research-constitution.yaml
git status --short --untracked-files=all
```

Expected: focused tests and readiness pass; baseline reports no new or changed failure; protected diff is empty; only exact discovery, audit, state-export, and registry-export artifacts are present.

- [ ] **Step 9: Export state and registry, then commit exact acceptance artifacts**

Run the existing state builder and registry exporter with the authoritative registry, inspect all changed paths, and stage each exact path explicitly. Do not stage an inbox directory. Commit:

```powershell
git commit -m "research(discovery): complete governed acceptance cycle"
```

Expected: a logical commit, clean versioned worktree, final audit with artifact hashes, empty temporary inboxes removed after successful ingestion, and no follow-up Campaign started.

---

## Plan Self-review Checklist

- [ ] Every design requirement maps to a task: roles and flow (Tasks 4-7), contracts (Tasks 1-2), sources and ranking (Tasks 1-2 and 5), registry/audit (Tasks 3 and 8), failure handling (Tasks 2 and 4-7), verification (Tasks 8-9).
- [ ] All new files have one responsibility and explicit interfaces.
- [ ] No task introduces a model provider, secret access, strategy mutation, Candidate, backtest, Campaign, Validation, or Holdout access.
- [ ] Function names and artifact fields are identical across tasks.
- [ ] The real acceptance cycle includes a human stop gate before approval.
- [ ] Exact-path staging is used throughout.

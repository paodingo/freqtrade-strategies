# Cross-Project Harness Protocol Design

- design_status: `approved`
- approved_by: `human_user`
- approved_at: `2026-07-15`
- protocol_stage: `design_only`
- authoritative_format: `Markdown`
- reference_projects:
  - `D:\code\freqtrade-strategies-clean`
  - `D:\code\ChinaSectorRadar`
  - `D:\book\rehab-intervention`

## 1. Purpose

This design defines a language-neutral Harness Protocol derived from three real projects at different maturity levels. The protocol creates a shared vocabulary and conformance boundary for governed agent work without forcing the projects to share one runtime, one role list, one storage engine, or one domain model.

The central decision is:

> Abstract the protocol now, validate it through project adapters, and defer a shared executable runtime until at least two projects prove the same semantics.

This document is incubated in `freqtrade-strategies-clean` because that repository currently contains the most complete Harness lifecycle. Incubation location does not make the Freqtrade domain model authoritative for the other projects.

## 2. Authorization Boundary

This design authorizes documentation only. It does not authorize:

- implementation or extraction of a shared Harness package;
- changes to any of the three project runtimes;
- execution of `ChinaSectorRadar` H1 Reliability Harness;
- migration of `rehab-intervention` to a multi-agent framework;
- refactoring of the Freqtrade discovery, Director, Campaign, registry, or execution paths;
- creation of a fourth repository, plugin, package, CLI, or shared service;
- broadening any existing phase, path, data, secret, deployment, trading, or production permission.

Every later implementation remains subject to the authority and approval rules of the project it changes.

## 3. Evidence Baseline

The three projects are complementary rather than uniformly mature.

The design baseline was inspected on `2026-07-15` from these versioned states:

| Project | Inspected HEAD | Primary authority and Harness evidence |
|---|---|---|
| `freqtrade-strategies-clean` | `087e620ab598c6ad39b44c2d2ebc9317bff755e9` | `AUTONOMY.md`, `research/governance/research-constitution.yaml`, `docs/superpowers/specs/2026-07-14-researcher-critic-discovery-design.md`, `scripts/research_discovery_*.py` |
| `ChinaSectorRadar` | `e895fb601a1d11d1b73c8c6b907abe250be573ea` | `AGENTS.md`, `docs/harness/h0_scope.md`, `docs/harness/h0_quality_baseline.md`, `docs/superpowers/plans/2026-07-14-h1-reliability-harness.md` |
| `rehab-intervention` | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` | `AGENTS.md`, `ARCHITECTURE.md`, `docs/harness-audit.md`, `harness/campaigns/phase2.json`, `scripts/harness-campaign.mjs` |

All three commit identities must be refreshed before any adapter implementation begins.

| Project | Strongest current Harness capability | Current limitation | Protocol contribution |
|---|---|---|---|
| `freqtrade-strategies-clean` | Researcher/Critic/Director separation, machine-readable Campaigns, fingerprints, registry, approval binding, deterministic control plane, contamination boundaries | Domain semantics and fixed repository paths are embedded deeply in implementation | Complete governed lifecycle and formal agent-role boundary |
| `ChinaSectorRadar` | Explicit Phase authority, exact-path scope, protected surfaces, role/file permissions, independent audit, separation of Harness completion from business readiness | H1 executable Reliability Harness is planned but not authorized or implemented | Authority chain, evidence truth, readiness, known-baseline blocker, independent review |
| `rehab-intervention` | Small executable Campaign runner with allowlist, budget, validation, retry, persisted state, resume, and secret-pattern stop | No product-level multi-agent framework; runner and Campaign are Phase 2 specific | Minimal executable task-control pattern and baseline-preserving adoption |

Maturity is evaluated on separate axes rather than as one score:

1. authority and governance;
2. executable control plane;
3. agent-role contracts;
4. state and registry integrity;
5. evidence and audit quality;
6. domain-data semantics;
7. portability and adapter isolation;
8. failure containment.

A less mature project is not required to imitate the most mature project. It is used to test whether a proposed abstraction remains useful when advanced capabilities are absent.

## 4. Goals

- Define a language-neutral protocol that can be represented with JSON Schema, JSON artifacts, Markdown evidence, and process exit semantics.
- Separate reusable Harness governance from project-specific policy and domain meaning.
- Define Agent as a governed role contract bound to a project and task, not as a universal autonomous object.
- Allow deterministic executors, model-backed roles, and human reviewers to participate in one governed workflow without pretending they are the same implementation type.
- Preserve exact permissions, explicit approvals, fail-closed behavior, baseline debt, provenance, and audit evidence.
- Support Python, PowerShell, and Node.js projects without choosing a shared runtime prematurely.
- Provide conformance rules that can be tested before code is moved into a shared package.

## 5. Non-Goals

The protocol does not:

- define one universal `BaseAgent` class;
- require every project to use Researcher, Critic, Director, or Campaign terminology;
- standardize project business states, data models, scoring logic, deployment procedures, or risk semantics;
- replace `AGENTS.md`, project Constitutions, phase contracts, quality baselines, or project-specific approval records;
- assume that a successful Harness run means the business system is healthy;
- require a shared database, queue, orchestration service, model provider, package manager, or programming language;
- convert optional role packs into mandatory Core features;
- hide historical failures or normalize `degraded` into `normal`;
- authorize production, live trading, market-data acquisition, database mutation, deployment, or secret access.

## 6. Design Principles

### 6.1 Contract coupling is required

Agents must be coupled to stable Harness contracts for permissions, inputs, outputs, approvals, and escalation. They must not be coupled directly to arbitrary repository paths, implicit chat history, or mutable project conventions.

### 6.2 Composition over inheritance

An executable Agent run is composed as:

```text
RoleContract
+ ProjectBinding
+ TaskManifest
+ CapabilityPolicy
+ Executor
= AgentRun
```

Roles do not inherit project permissions. The ProjectBinding and TaskManifest narrow the role for one project and one run.

### 6.3 Protocol before runtime

The first shared artifact is a protocol and conformance suite. Runtime implementation language, package shape, and repository ownership remain deliberately deferred until adapters prove that the contract is stable.

### 6.4 Fail closed without erasing uncertainty

Unknown permission, invalid schema, missing evidence, stale binding, illegal transition, unavailable tool, or ambiguous authority must not silently pass. The protocol distinguishes a governed block from an infrastructure or tool error.

### 6.5 Existing project authority wins

The shared protocol may narrow authority but may never widen the permissions granted by the current project phase, Constitution, task, approval, or human decision.

### 6.6 Evidence is part of the result

A completion claim is incomplete without the evidence paths, command outcomes, relevant fingerprints or identities, known blockers, and final authority state required by the project.

## 7. Layered Architecture

```text
Cross-Project Harness Protocol
├── Core Contracts
│   ├── authority
│   ├── task and capability scope
│   ├── budgets and stop conditions
│   ├── normalized gate and run outcomes
│   ├── approvals and escalation
│   └── evidence and conformance
├── Role Packs
│   ├── research-discovery
│   ├── audit-and-review
│   └── implementation-and-review
├── Project Adapters
│   ├── freqtrade-strategies-clean
│   ├── ChinaSectorRadar
│   └── rehab-intervention
└── Executors
    ├── model-backed role
    ├── deterministic process
    ├── human decision
    └── project-local runner
```

Core Contracts contain no project name, trading pair, business entity, framework path, dataset identifier, scheduler name, database table, strategy family, or UI concept.

Role Packs are optional workflow modules. Project Adapters map existing project terminology and evidence into Core Contracts. Executors remain project-local in the first version.

## 8. Core Contract Model

The protocol defines logical contracts first. Exact JSON Schema files are an implementation-stage deliverable and are not created by this design.

### 8.1 `ProjectBinding`

Required logical fields:

- `protocol_version`
- `project_id`
- `project_root_identity`
- `authority_sources`
- `phase_source`
- `policy_sources`
- `runtime_entries`
- `state_backend`
- `evidence_roots`
- `adapter_version`

`ProjectBinding` tells the protocol how to locate current authority and evidence. It does not grant permission by itself.

### 8.2 `PhaseAuthority`

Required logical fields:

- `phase_id`
- `authority_fingerprint`
- `approved_operations`
- `forbidden_operations`
- `protected_surfaces`
- `next_phase`
- `next_phase_requires_human_approval`
- `effective_at`

Any phase change invalidates task authorization derived from the previous phase unless the project explicitly proves compatibility.

### 8.3 `RoleContract`

Required logical fields:

- `role_id`
- `role_pack`
- `accepted_input_contracts`
- `produced_output_contracts`
- `allowed_capabilities`
- `forbidden_capabilities`
- `approval_authority`
- `self_approval_allowed`
- `escalation_conditions`

`self_approval_allowed` defaults to `false`. A role may be implemented by a model, deterministic code, or a human, but the implementation type does not change its authority.

### 8.4 `TaskManifest`

Required logical fields:

- `task_id`
- `project_id`
- `phase_id`
- `role_id`
- `objective`
- `input_bindings`
- `allowed_paths`
- `blocked_paths`
- `capabilities`
- `budgets`
- `validation_commands`
- `expected_outputs`
- `stop_conditions`
- `required_approvals`
- `authority_fingerprint`

`blocked_paths` always wins over `allowed_paths`. An absent or ambiguous permission is denied.

### 8.5 `CapabilityPolicy`

Capabilities use namespaced identifiers so project-local capabilities do not pollute Core:

```text
core.read_repository
core.write_allowlisted_artifact
core.run_validation
core.record_evidence
research.propose_direction
research.execute_backtest
market.acquire_data
ops.run_scheduler
database.write
deploy.publish
```

Core defines the capability mechanism, not the full global capability list. Project adapters register project-specific namespaces and bind them to concrete tools and paths.

### 8.6 `Budget`

Core budget dimensions may include:

- `max_attempts`
- `max_tasks`
- `max_wall_clock_seconds`
- `max_changed_files`
- `max_output_bytes`
- `max_external_calls`
- `max_data_accesses`

Projects may add namespaced dimensions. Missing budget dimensions are not assumed to be unlimited; the project policy must state whether they are not applicable or separately governed.

### 8.7 `GateResult`

Normalized outcomes:

| `outcome` | Meaning | Process category |
|---|---|---|
| `passed` | The gate completed and its condition holds | success |
| `blocked` | The gate completed and found a governed violation or unmet condition | policy/business block |
| `error` | The gate could not make a trustworthy determination | tool/environment/configuration error |

Portable process exit mapping is:

```text
0 → passed
1 → blocked
2 → error
```

Projects may retain richer local statuses, but every shared gate must map deterministically to one normalized outcome and preserve the original local reason code.

### 8.8 `RunState`

Normalized lifecycle states:

```text
planned → ready → running → completed
                         ↘ stopped
                         ↘ failed
                         ↘ escalated
```

- `completed` means the authorized task or queue ended normally; it does not imply business readiness.
- `stopped` means an expected stop condition fired.
- `failed` means the execution or control plane could not complete reliably.
- `escalated` means new human authority is required.

Project-local states such as `blocked`, `degraded`, `no_research_recommended`, or `h0_baseline_failed` remain preserved in project evidence and map to Core only for cross-project reporting.

### 8.9 `ApprovalRecord`

Required logical fields:

- `approval_id`
- `approver_type`
- `approved_action`
- `bound_artifacts`
- `bound_fingerprints`
- `scope`
- `decided_at`
- `expires_at` or explicit non-expiry policy
- `approval_fingerprint`

Content, authority, phase, or governed-state changes invalidate approval unless the project supplies an explicit compatibility rule.

### 8.10 `EscalationRecord`

Required logical fields:

- `reason_code`
- `blocked_action`
- `current_phase`
- `required_authority`
- `evidence_refs`
- `safe_resume_condition`
- `created_at`

Escalation does not grant the requested authority and does not automatically retry.

### 8.11 `EvidenceBundle`

Required logical fields:

- `run_id`
- `project_id`
- `task_id`
- `authority_snapshot`
- `input_identities`
- `gate_results`
- `command_results`
- `artifact_refs`
- `known_baseline_debt`
- `open_blockers`
- `business_readiness`
- `harness_completion`
- `final_run_state`
- `generated_at`

`business_readiness` and `harness_completion` are independent fields. A Harness can complete successfully while correctly proving that business readiness is blocked.

## 9. Role Packs

Core defines `RoleContract`; it does not define a mandatory role hierarchy.

### 9.1 Research-discovery role pack

Initial roles:

- `Researcher`
- `ResearchCritic`
- `HumanDirectionReviewer`
- `ResearchDirector`
- `CampaignOrchestrator`
- `Evaluator`
- `Gatekeeper`

This pack is derived from Freqtrade but remains optional. Its project adapter owns market, dataset, contamination, Candidate, Validation, Holdout, and execution semantics.

### 9.2 Audit-and-review role pack

Initial roles:

- `Coordinator`
- `DataResearcher`
- `Developer`
- `SpecReviewer`
- `QualityReviewer`
- `IndependentAuditor`

This pack captures staged audit and independent-review workflows such as `ChinaSectorRadar` H0. It does not create a Product Manager role and does not let reviewers edit the work they approve.

### 9.3 Implementation-and-review role pack

Initial roles:

- `Implementer`
- `Reviewer`
- `Verifier`

This is the smallest role pack for ordinary application work. `rehab-intervention` may use it later without adopting research-discovery roles.

### 9.4 Role-pack admission rule

A role belongs in a shared role pack only when:

- its authority boundary is explicit;
- its input and output contracts are testable;
- its self-approval behavior is explicit;
- at least one real workflow needs it;
- it does not require Core to understand project-domain semantics.

## 10. Project Adapter Mappings

### 10.1 Freqtrade adapter

| Existing concept | Protocol mapping |
|---|---|
| `research/governance/research-constitution.yaml` | `PhaseAuthority` and project policy source |
| Researcher/Critic/Director contracts | research-discovery `RoleContract` instances |
| Campaign YAML | `TaskManifest` plus project execution extension |
| Director Registry | project `state_backend` and event evidence |
| fingerprints and approvals | `ApprovalRecord` binding |
| Validation/Holdout/Candidate boundaries | project capability and data-governance extension |
| readiness and guard scripts | `GateResult` producers |

The adapter must remove Freqtrade literals from Core rather than rename them generically.

### 10.2 ChinaSectorRadar adapter

| Existing concept | Protocol mapping |
|---|---|
| `AGENTS.md` and `docs/harness/h0_scope.md` | `PhaseAuthority` sources |
| exact H0 write paths and protected surfaces | `TaskManifest` path policies |
| Coordinator/Data researcher/review roles | audit-and-review `RoleContract` instances |
| H0 audit JSON/Markdown/HTML | `EvidenceBundle` |
| planned H1 task manifest | future `TaskManifest` implementation |
| planned readiness `0/1/2` | `GateResult` process mapping |
| scheduler/log/index/health-check truth split | project evidence and readiness extension |

This mapping does not authorize H1. H1 remains behind its existing user-approval gate.

### 10.3 Rehab-intervention adapter

| Existing concept | Protocol mapping |
|---|---|
| `AGENTS.md` and quality baseline | authority and project policy sources |
| `harness/campaigns/phase2.json` | early `TaskManifest` shape |
| `scripts/harness-campaign.mjs` | project-local executor |
| `allowed_paths` and `changed_paths` | path-policy inputs |
| `max_attempts`, `max_changed_files`, `max_seconds` | `Budget` |
| validation results | `GateResult` producers |
| `harness/state/*.state.json` | project-local `RunState` backend |
| auth/session/database/deploy constraints | project capability extensions |

This adapter does not add a product multi-agent framework. It standardizes only the Harness-facing contract.

## 11. Cross-Project Admission Rules

The protocol uses a two-of-three rule:

1. at least two projects need materially identical semantics;
2. the third project does not contradict the abstraction;
3. the behavior can be specified and tested without importing a project-domain concept;
4. the abstraction preserves stricter project-local policy;
5. the abstraction has a clear failure mode.

Classification rules:

- shared by at least two projects and domain-neutral → Core candidate;
- shared workflow role but not universal → Role Pack;
- specific to one project domain or runtime → Project Adapter;
- speculative convenience with no second consumer → defer;
- weakens any existing guard, approval, audit, or evidence rule → reject.

Initial classification:

| Capability | Classification |
|---|---|
| phase and human authority | Core |
| exact/narrow path permissions | Core |
| budgets and stop conditions | Core |
| normalized gate outcomes | Core |
| persisted run state | Core contract, project-local backend |
| evidence bundle and known debt | Core |
| approval fingerprint binding | Core optional capability until second adapter proves full semantics |
| Researcher/Critic/Director | research-discovery Role Pack |
| independent auditor | audit-and-review Role Pack |
| Validation/Holdout contamination | Freqtrade adapter |
| provider/scheduler/report freshness | ChinaSectorRadar adapter |
| auth/session/Prisma/deployment mutation | rehab-intervention adapter |

## 12. Protocol Data Flow

```text
Project authority sources
        ↓
Project Adapter → canonical authority/task/role snapshot
        ↓
Protocol conformance validation
        ↓
Project-local Executor performs only authorized operations
        ↓
GateResult + local reason codes + artifacts
        ↓
RunState transition
        ↓
EvidenceBundle
        ↓
Human approval, completion, stop, failure, or escalation
```

The Adapter is responsible for lossless mapping. If a local concept cannot be represented without losing a safety distinction, the Adapter must retain it as a namespaced extension or reject conformance.

## 13. Failure Handling

- Invalid or unknown protocol version → `error`.
- Missing authority source or stale authority fingerprint → `blocked` when the mismatch is known; otherwise `error`.
- Path outside allowlist or inside blocked/protected surface → `blocked` and no retry without new authority.
- Secret-like material or private credential request → `escalated`; secret contents are not copied into evidence.
- Budget exhaustion → `stopped` with consumed-budget evidence.
- Validation command returns an unrecognized outcome → `error`.
- Business readiness blocker found by a correctly operating Harness → Harness may be `completed` while `business_readiness` remains blocked or degraded.
- Project adapter loses local reason codes, evidence identities, or authority bindings → conformance failure.
- Approval fingerprint mismatch → approval invalidation, not automatic reapproval.
- Retry never widens scope, refreshes budget, changes policy, or crosses a phase gate.

## 14. Conformance Model

### 14.1 Protocol contract tests

- Valid canonical artifacts pass their schema.
- Missing required fields, unknown critical fields, and invalid enum values fail closed.
- Canonical fingerprints are stable for normalized identical content.
- Authority or governed-content changes invalidate dependent approvals and task bindings.
- `blocked_paths` overrides `allowed_paths`.

### 14.2 State and gate tests

- Identical local outcomes map to identical normalized `GateResult` values.
- Exit codes `0/1/2` map to `passed/blocked/error` where a process entry implements the portable convention.
- Illegal state transitions fail without modifying persisted state.
- Resume continues only from an explicitly resumable state and does not recharge consumed budget.

### 14.3 Evidence tests

- Evidence names the authority snapshot, task, commands, outputs, blockers, and final state.
- Harness completion and business readiness remain independently testable.
- Historical baseline debt remains visible.
- Sensitive findings contain location and risk, not secret contents.
- Evidence freshness rules are supplied and tested by the project adapter.

### 14.4 Role-boundary tests

- A role cannot call a capability absent from its contract and TaskManifest.
- A reviewer cannot silently edit the artifact it approves.
- A role with `self_approval_allowed: false` cannot create a valid approval for its own output.
- Model-backed and deterministic implementations of one role produce the same contract shape even when their internal behavior differs.

### 14.5 Adapter golden fixtures

Each project adapter supplies at least:

- one conforming normal fixture;
- one governed block fixture;
- one tool/environment error fixture;
- one authority mismatch fixture;
- one known-baseline-debt fixture.

Golden fixtures contain synthetic or approved non-secret evidence. They must not copy production secrets, private data, or protected historical artifacts.

## 15. Staged Adoption

### Stage P0 — Design and vocabulary

- Produce this design and its Chinese HTML companion.
- Make no runtime or project Harness changes.
- Confirm the Core/Role Pack/Adapter separation with the user.

### Stage P1 — Protocol schemas and synthetic conformance fixtures

- Create language-neutral schemas and synthetic fixtures in a separately approved task.
- Test the protocol without importing any of the three project runtimes.
- Keep implementation language and repository extraction deferred.

### Stage P2 — Read-only project mappings

- Implement or document one read-only adapter mapping per project.
- Prove that current authority, state, and evidence can be represented without weakening local rules.
- Do not replace project-local runners.

### Stage P3 — Second-consumer pilot

- Select the next independently approved Harness phase in one lower-maturity project.
- Use the shared protocol as a compatibility boundary while preserving its local runtime.
- Measure how much Core changes are required.

Candidate pilots are a separately approved `ChinaSectorRadar` H1 execution or a future `rehab-intervention` Campaign iteration. This design selects neither and grants authority to neither.

### Stage P4 — Runtime extraction decision

A standalone package, CLI, plugin, or repository may be proposed only when:

- at least two project adapters pass conformance;
- the second project does not require domain literals in Core;
- adapter-only differences remain isolated;
- Core behavior is stable across at least two real governed runs;
- runtime distribution and upgrade ownership are explicit;
- rollback to project-local Harness behavior is defined.

## 16. Deliberately Deferred Decisions

These decisions are not missing requirements; they are intentionally deferred until adapter evidence exists:

- implementation language for any shared CLI or library;
- ownership repository for shared artifacts;
- package manager and distribution mechanism;
- state storage implementation;
- model-provider interface;
- whether approval fingerprints are mandatory for every low-risk task;
- whether Core ships built-in role packs or references separately versioned packs;
- whether a Codex skill or plugin becomes a distribution surface.

No implementation plan may silently decide these items. A later design amendment or implementation-specific design must make each selected choice explicit.

## 17. Success Criteria

The protocol design succeeds when:

- all three projects can map their current Harness concepts without pretending to have capabilities they do not possess;
- Core contains no Freqtrade, China-market, rehab, framework, database, scheduler, strategy, or UI domain literal;
- stricter project rules always override shared defaults;
- agent roles are reusable contracts rather than hidden project permissions;
- a business-readiness failure can coexist with correct Harness completion;
- conformance can be tested using synthetic fixtures before any shared runtime exists;
- the second-consumer pilot can proceed without a broad rewrite of the first project;
- future extraction decisions are evidence-driven rather than based on one mature implementation.

## 18. Current Decision and Next Gate

The approved current direction is `protocol_first`. The next allowed design activity is a separately reviewed P1 specification for protocol schemas and synthetic conformance fixtures.

This document does not itself authorize P1 implementation. No code extraction, adapter implementation, project migration, or Harness phase execution begins until the user approves the corresponding project-specific plan and write surface.

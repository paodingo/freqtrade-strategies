# Researcher and Research Critic Discovery Layer Design

## 1. Purpose

This design adds a governed research-discovery layer in front of the existing Research Director. It addresses a specific gap: the current system can rank and govern known, evidence-linked proposals, but it does not provide a broad, independent mechanism for discovering new research directions and entirely different strategy families.

The discovery layer must let a non-specialist human reviewer make an informed portfolio decision without asking that reviewer to judge whether a quantitative hypothesis will be profitable. The system must explain why a direction is worth investigating, why it may be wrong, what it will cost, and what evidence would stop it.

The approved flow is:

`event trigger -> Researcher -> Research Critic -> Top 3 -> human direction review -> Research Director -> execution-risk approval -> Campaign`

Direction approval means only that an idea is worth formal preparation. It is not authorization to create a Candidate, mutate a strategy, access protected data, or execute a Campaign.

## 2. Goals

- Discover evidence-linked research directions that are not limited to incremental changes to `RegimeAwareV6`.
- Permit entirely different strategy families while holding the initial market, data, runtime, timeframe, and risk boundaries fixed.
- Produce a maximum of three plain-language, ranked directions per discovery cycle.
- Require an independent adversarial critique before human review.
- Preserve the existing Research Director as the sole component that converts an approved direction into `research-proposal-v1` and applies formal governance.
- Make `no_research_recommended` a valid and expected result.
- Preserve full provenance, deterministic ranking, immutable approval fingerprints, and append-only audit evidence.

## 3. Non-goals

The discovery layer does not:

- create or edit strategy code;
- create a Candidate;
- run a backtest, Campaign, hyperopt, or live/dry-run trading process;
- access Validation results, Holdout data, private APIs, secrets, or live account data;
- acquire and silently incorporate a new market dataset;
- change leverage, stake, stoploss, ROI, protections, position stacking, position adjustment, or other risk semantics;
- approve its own direction or authorize execution;
- reopen a closed research branch;
- replace the Research Director, the Research Constitution, or existing approval routes;
- rank ideas by promised return, win rate, or headline backtest performance.

## 4. Fixed First-version Scope

The first version may propose any strategy family, including trend following, mean reversion, breakout, volatility, regime switching, market microstructure, or another falsifiable family. It must keep the following comparison envelope fixed:

- exchange and market: Binance USD-M Futures;
- margin mode: isolated;
- approved local Development market data only;
- approved BTC and ETH Development datasets only where their existing manifests permit the intended analysis;
- primary timeframe: `1h`;
- informative timeframe: `4h`;
- existing immutable runtime, execution, split, and evaluation contracts;
- existing risk controls and risk parameters;
- no new pair, timeframe, dataset, Validation feedback, or Holdout access.

An idea that requires a scope change may be described, but it must be classified as `out_of_v1_scope` and cannot enter the shortlist. A missing dataset produces a data-readiness recommendation, not a strategy Campaign.

## 5. Roles and Authority

### 5.1 Discovery Trigger Controller

The controller starts a discovery cycle only for one of these events:

- a Campaign completes;
- a research branch is formally closed;
- the Research Director returns `no_research_recommended`;
- a human explicitly requests a discovery cycle.

Each trigger includes an event identifier, event type, current research-state fingerprint, Constitution fingerprint, allowed-source policy version, and creation time. The trigger fingerprint makes repeated delivery idempotent.

### 5.2 Researcher

The Researcher reads only approved sources and produces six to ten `research-idea-v1` artifacts per cycle. It may propose entirely different strategy families, but it may emit no more than two ideas from one family in a cycle.

The Researcher owns idea generation and source attribution. It does not own critique, approval, proposal compilation, or execution. It cannot modify an idea after that version has entered critique; a revision creates a new version and fingerprint.

### 5.3 Research Critic

The Research Critic runs as a separate review stage with no authority to edit the Researcher's artifact. It independently checks source support, contradictory evidence, duplication, falsifiability, data readiness, leakage, overfitting, cost realism, transaction-cost sensitivity, and plausible failure modes.

Its verdict is one of:

- `pass`: eligible for ranking;
- `revise`: not eligible until a new immutable idea version receives a fresh critique;
- `reject`: ineligible for the current cycle.

At most one Researcher revision is allowed for an idea in one cycle. This prevents unbounded Researcher-Critic loops.

### 5.4 Human Direction Reviewer

The human receives a Chinese review packet containing at most three ideas. Machine-facing keys and enumerated values remain English.

The reviewer decides whether a direction is worth formal preparation. The reviewer may select at most one idea for handoff in a cycle, matching the Constitution's one-Campaign portfolio budget. Other ideas are `rejected` or `deferred`; deferred ideas do not execute automatically in a later cycle.

The reviewer's decision is bound to the shortlist fingerprint, idea fingerprint, critique fingerprint, research-state fingerprint, and Constitution fingerprint. Any change invalidates the approval.

### 5.5 Research Director

The Research Director accepts only one selected, human-approved, fingerprint-valid handoff. It converts the direction into the existing `research-proposal-v1` contract and independently repeats all closure, duplication, evidence, dataset, runtime, budget, contamination, risk, and approval-route checks.

The Director may reject the handoff. A rejection is terminal for that idea version and is returned to discovery as evidence for future cycles; it does not cause an automatic rewrite or retry.

Human direction approval does not satisfy a later medium- or high-risk execution approval. Existing Constitution routes remain authoritative. In particular, a new Candidate or strategy structure remains subject to explicit execution authorization.

## 6. Data Contracts

### 6.1 `research-trigger-v1`

Required fields:

- `schema_version`
- `trigger_id`
- `event_type`
- `event_ref`
- `research_state_fingerprint`
- `constitution_fingerprint`
- `source_policy_version`
- `created_at`
- `trigger_fingerprint`

### 6.2 `research-idea-v1`

Required fields:

- `schema_version`
- `idea_id`
- `idea_version`
- `strategy_family`
- `title`
- `plain_language_summary_zh`
- `falsifiable_hypothesis`
- `proposed_market_mechanism`
- `supporting_evidence`
- `contradictory_evidence`
- `source_refs`
- `novelty_vs_existing_research`
- `required_datasets`
- `data_readiness`
- `fixed_scope_confirmation`
- `minimal_test_method`
- `comparison_baseline`
- `expected_information_gain`
- `estimated_cost`
- `risk_class`
- `contamination_risk`
- `falsification_conditions`
- `stop_conditions`
- `known_limitations`
- `research_state_fingerprint`
- `semantic_fingerprint`

The artifact contains no strategy implementation and no projected return promise.

### 6.3 `research-critique-v1`

Required fields:

- `schema_version`
- `critique_id`
- `idea_id`
- `idea_semantic_fingerprint`
- `verdict`
- `source_verification`
- `duplicate_research_check`
- `falsifiability_assessment`
- `data_readiness_assessment`
- `leakage_and_overfit_risks`
- `transaction_cost_challenge`
- `strongest_counterevidence`
- `alternative_explanations`
- `fatal_objections`
- `score_adjustments`
- `ranking_inputs`
- `critic_fingerprint`

`ranking_inputs` supplies the five normalized component values used by the deterministic ranking policy. Each value must be justified by the critique; the shortlist builder does not invent or infer missing values.

### 6.4 `research-shortlist-v1`

Required fields:

- `schema_version`
- `discovery_run_id`
- `eligible_idea_count`
- `ranking_policy_version`
- `ranked_ideas`
- `recommended_idea_id`
- `recommendation`
- `recommendation_reason_zh`
- `research_state_fingerprint`
- `shortlist_fingerprint`

`ranked_ideas` contains zero to three entries. `recommended_idea_id` is nullable. An empty list requires `recommended_idea_id: null` and `recommendation: no_research_recommended`.

### 6.5 `research-direction-approval-v1`

Required fields:

- `schema_version`
- `discovery_run_id`
- `decision`
- `selected_idea_id`
- `selected_idea_fingerprint`
- `selected_critique_fingerprint`
- `shortlist_fingerprint`
- `research_state_fingerprint`
- `constitution_fingerprint`
- `reviewer_type`
- `decision_reason_zh`
- `decided_at`
- `approval_fingerprint`

`decision` is `approved_for_director_handoff`, `rejected`, or `deferred`. `selected_idea_id`, `selected_idea_fingerprint`, and `selected_critique_fingerprint` are nullable only for `rejected` or `deferred`. Only `approved_for_director_handoff` permits a handoff and requires all three values.

### 6.6 `research-direction-handoff-v1`

The handoff contains the approved idea and critique references, approval reference, all bound fingerprints, proposed `research_question`, and a declaration that execution is not authorized. It never contains a Candidate or executable Campaign.

## 7. State Machine

The successful handoff path is:

`discovered -> criticized -> shortlisted -> human_approved -> handed_to_director -> converted | director_rejected`

From `shortlisted`, `rejected` and `deferred` are terminal states for the current cycle and cannot transition to `handed_to_director`.

Additional terminal or side states are:

- `critic_rejected`
- `revision_exhausted`
- `out_of_v1_scope`
- `insufficient_source_evidence`
- `data_readiness_required`
- `fingerprint_invalidated`
- `no_research_recommended`

No state transition directly reaches Candidate creation, Campaign compilation, or execution.

## 8. Source Governance

### 8.1 Source Classes

- Class A: frozen repository datasets, completed research artifacts, Research Registry records, branch closures, approved governance artifacts, and official exchange documentation.
- Class B: peer-reviewed papers, reputable preprints, textbooks, and credible institutional research reports.
- Class C: public strategy repositories, blogs, forums, social media, videos, rankings, and commercial claims.

An idea needs at least one Class A or Class B source to pass critique. Class C may inspire an idea but cannot support a conclusion; a Class C-only idea is rejected.

### 8.2 External-source Record

Every external source record includes:

- canonical URL;
- source class and publisher type;
- retrieval timestamp;
- publication timestamp when available;
- the specific claim it supports or contradicts;
- content fingerprint or immutable retrieval handle when available;
- staleness assessment;
- licensing or quotation constraints.

Only source metadata, short compliant excerpts when needed, and the Researcher's own summary are stored. The system does not copy entire copyrighted works into the repository.

### 8.3 Data Discovery Versus Acquisition

The Researcher may state that an idea requires open interest, order book, liquidation, basis, another pair, or another public data type. It may not download that data or treat it as available. Such an idea becomes `data_readiness_required` and needs a separate, human-approved acquisition scope before future consideration.

## 9. Candidate Generation and Ranking

Each cycle begins with six to ten ideas, capped at two per strategy family. Only `pass` critiques enter ranking.

Each scored component is normalized to `[0, 1]`:

```text
base_score =
    0.30 * expected_information_gain
  + 0.20 * falsifiability_and_mechanism_clarity
  + 0.20 * feasibility_with_existing_data
  + 0.15 * novelty_and_non_duplication
  + 0.15 * robustness_relevance

final_score = base_score
  - risk_penalty
  - cost_penalty
  - contamination_penalty
  - source_penalty
```

Initial policy penalties are:

| Factor | Value | Penalty or result |
|---|---|---|
| Risk | low / medium / high / forbidden | `0.00` / `0.05` / `0.15` / reject |
| Cost | low / medium / high | `0.00` / `0.03` / `0.08` |
| Contamination | none / low / medium / high | `0.00` / `0.02` / `0.08` / reject |
| Sources | includes Class A / Class B without A / Class C only | `0.00` / `0.02` / reject |

The scoring policy is versioned. It cannot be changed inside a discovery run.

An idea must have `final_score >= 0.55` to enter the shortlist. Ties are resolved by lower risk, then lower cost, then the lexical order of `semantic_fingerprint`. This makes ranking reproducible for identical inputs.

Expected return, backtest profit, and win rate are not scoring inputs. The output contains at most three ideas. If no idea crosses the threshold, the cycle completes successfully with `no_research_recommended`.

## 10. Human Review Packet

The human-facing packet is Chinese-first and contains, for each shortlisted idea:

- what the system proposes to study;
- why it may matter now;
- what mechanism could make it work;
- the strongest reason it may be wrong;
- which data already exist and which do not;
- the smallest useful experiment;
- likely time, compute, and governance cost;
- what result would stop the direction;
- the Critic verdict and score adjustments;
- the system's recommendation and uncertainty.

The packet explicitly states that approving a direction is not a claim of profitability and is not execution authorization.

Every user-facing Markdown document in this discovery scope also has a self-contained Simplified Chinese `.zh-CN.html` reading companion beside it. Markdown and machine-readable artifacts remain authoritative. The HTML copy must work offline, remain readable at desktop and mobile widths, print cleanly, expose source provenance, and preserve code, paths, commands, schema names, keys, enums, and exact policy values in English.

## 11. Failure Handling

- Missing or unverifiable source evidence produces `insufficient_source_evidence`.
- Missing required data produces `data_readiness_required` and no strategy Campaign.
- Duplicate research is rejected with references to the existing evidence.
- A missing Critic artifact blocks shortlist generation.
- A source, idea, critique, state, Constitution, or shortlist fingerprint mismatch invalidates approval.
- If external retrieval is unavailable, the run may continue with repository sources only and records `source_coverage: internal_only_degraded`; it may not pretend an external review occurred.
- A Research Director rejection is recorded as terminal evidence for that idea version and does not trigger an automatic retry.
- Re-delivery of the same trigger fingerprint returns the existing run without producing new ideas.
- No qualifying ideas completes normally with `no_research_recommended`.
- Any attempt to access a forbidden path, Validation result, Holdout, private API, secret, strategy mutation path, Candidate path, or execution runner stops and escalates the run.

## 12. Audit and Storage

Discovery artifacts use a bounded, reviewable path surface:

Angle-bracketed segments below are runtime identifier slots, not unresolved design placeholders.

```text
research/discovery/schemas/research-trigger.schema.json
research/discovery/schemas/research-idea.schema.json
research/discovery/schemas/research-critique.schema.json
research/discovery/schemas/research-shortlist.schema.json
research/discovery/schemas/research-direction-approval.schema.json
research/discovery/schemas/research-direction-handoff.schema.json
research/discovery/policy/source-policy.yaml
research/discovery/policy/ranking-policy.yaml
research/discovery/runs/<run-id>/trigger.json
research/discovery/runs/<run-id>/ideas/<idea-id>-v<version>.json
research/discovery/runs/<run-id>/critiques/<idea-id>-v<version>.json
research/discovery/runs/<run-id>/shortlist.json
research/discovery/runs/<run-id>/human-review.md
research/discovery/runs/<run-id>/human-review.zh-CN.html
research/discovery/runs/<run-id>/approval.json
research/discovery/runs/<run-id>/handoff.json
reports/audits/research-discovery/<run-id>-final-report.json
reports/audits/research-discovery/<run-id>-final-report.md
reports/audits/research-discovery/<run-id>-final-report.zh-CN.html
```

Implementation must add exact-path or narrowly enumerated guard entries for these surfaces rather than broad `research/**`, `reports/**`, or staging rules.

The existing Director Registry remains the authoritative registry. New append-only records cover discovery runs, idea versions, critiques, shortlist decisions, human decisions, fingerprint invalidations, and Director handoff results. Human-facing Markdown and HTML are Chinese; machine-facing schemas, keys, enums, and registry fields are English.

## 13. Verification and Acceptance

### 13.1 Contract Tests

- All six schemas accept complete valid artifacts and reject missing required fields.
- Unknown or illegal state transitions fail closed.
- Fingerprints are stable for normalized identical content and change when governed content changes.
- Approval validates every bound fingerprint.
- Handoff accepts only `approved_for_director_handoff` and declares `execution_authorized: false`.

### 13.2 Role-boundary Tests

- Researcher code cannot invoke an experiment, Campaign, Candidate, or strategy mutation path.
- Critic code cannot edit or replace an idea artifact.
- Neither role can access Validation results, Holdout, secrets, private APIs, or live data.
- A new strategy family is accepted as an idea while out-of-scope market, timeframe, dataset, or risk changes are blocked.

### 13.3 Ranking Tests

- Identical inputs produce identical scores, tie-breaks, and ordering.
- No strategy family contributes more than two initial ideas.
- No more than three ideas appear in a shortlist.
- Class C-only, forbidden-risk, high-contamination, duplicate, and below-threshold ideas are excluded.
- An empty eligible set produces `no_research_recommended`.

### 13.4 Workflow Tests

- Campaign completion, branch closure, Director exhaustion, and manual request produce valid triggers.
- The same trigger fingerprint is idempotent.
- Critic `revise` requires a new version and permits at most one revision per cycle.
- Human review selects at most one handoff.
- A post-approval content or state change invalidates the approval.
- A Director rejection records evidence and does not retry automatically.
- The handoff converts cleanly into the existing `research-proposal-v1` input boundary without bypassing Director checks.

### 13.5 End-to-end Dry Run

The acceptance dry run must demonstrate all of the following:

- event-triggered generation of six to ten ideas across multiple families;
- independent critiques;
- deterministic Top 3 or `no_research_recommended`;
- readable Chinese Markdown and self-contained `.zh-CN.html` human-review packets;
- a fingerprint-bound human decision;
- a valid Director handoff with no execution authorization;
- zero Candidates created;
- zero Campaigns started;
- zero Validation or Holdout accesses;
- zero strategy or risk mutations;
- complete registry and artifact-integrity evidence;
- targeted tests, readiness checks, baseline verification, guard review, logical commit, and a clean versioned worktree.

## 14. Success Criteria

The discovery layer is successful when a non-specialist human can choose whether one of at most three clearly explained, adversarially reviewed directions deserves formal preparation, while the repository proves that discovery itself performed no strategy implementation or experiment and that the existing Research Director and Constitution retained full execution authority.

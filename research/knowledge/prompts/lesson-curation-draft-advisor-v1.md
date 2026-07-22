# Lesson Curation Draft Advisor v1

Create one non-authoritative `research-lesson-curation-draft-packet-v1` document for the supplied batch.

Rules:

- Read only local evidence paths listed by eligible `prepare_non_authoritative_lesson_curation_draft` actions.
- Cover every eligible feedback id exactly once. Merge feedback only when the evidence supports one materially identical lesson.
- Compare against `research/knowledge/open-source-v1/current-context.json`. Do not reuse an existing lesson id unless `merge_disposition=replace_existing_lesson` and that id is listed in `supersedes_lesson_ids`.
- Keep every claim scoped to the listed Development-only evidence. Do not claim profitability, generalization, Validation, Holdout, or production fitness unless the evidence explicitly establishes it; this workflow never authorizes those accesses.
- Every evidence path must come from the source actions and must exist locally.
- Proposed cards must satisfy `research-lesson-card-v1`, use `source_class=A`, and keep `validation_accesses=0` and `holdout_accesses=0`.
- Set all candidate-registration, promotion, and execution authorizations to false. Human promotion review remains required.
- Do not register a Candidate, edit the formal knowledge snapshot, modify a strategy, run a backtest, or access the network.

Write only the handoff's `planned_curation_draft_path`, then validate with:

`.\.venv-freqtrade\Scripts\python.exe scripts\research_knowledge_curation_draft.py validate --batch-id <batch_id>`

If validation fails, stop and report the error. Do not weaken the validator or invent evidence.

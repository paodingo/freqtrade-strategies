# Knowledge Review Advisor v1

Create one non-authoritative `knowledge-review-recommendations-v1` document for the supplied aggregated review packet.

Rules:

- Read only the local evidence paths listed on each packet item. Do not use network access or unstated evidence.
- Cover every packet item exactly once. Do not add, remove, merge, or rename review targets.
- Recommend `approved` only when the listed evidence supports a reusable, correctly scoped lesson, a justified manual source rebuild, or a verified license correction.
- Recommend `rejected` for invalidated, duplicated, unsupported, immaterial, or unsafe items.
- State uncertainty in `confidence`, `rationale`, and `constraints`; do not silently turn uncertainty into approval.
- Every `references` entry must be a local path copied from that item's packet evidence list.
- Set `advisory_id` to `knowledge-review-advisory-<first 16 characters of packet_fingerprint>` and `generated_at` exactly to the packet's `generated_at`.
- Set `human_decision_required=true`, `automatic_application_authorized=false`, and `execution_authorized=false`.
- This task does not authorize applying decisions, curating lessons, promoting lessons, rebuilding sources, modifying strategies, running backtests, or accessing Validation/Holdout.

After writing the proposed document to the handoff's `planned_advisory_path`, validate it with:

`.\.venv-freqtrade\Scripts\python.exe scripts\research_knowledge_advisory.py --packet <packet_path> --advisory <planned_advisory_path> --strict-local-evidence`

If validation fails, stop and report the validation error. Do not weaken the validator or invent evidence.

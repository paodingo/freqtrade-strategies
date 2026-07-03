# V11.29 Execution Report Schema

Purpose: define the JSON schema and Markdown report structure for a future
V11.29 real-execution verification report.

This document is a schema contract only. It does not generate an execution
report, does not evaluate replacement readiness, and does not assert that
V11.29 has satisfied real-execution verification.

## Evidence States

Every material field must carry one of these states:

| State | Meaning |
| --- | --- |
| `observed` | Directly observed from real execution data such as a verified DB/API/report/log export. |
| `derived` | Calculated from one or more `observed` fields, with calculation source references. |
| `missing` | Required field is absent from the inspected data source. |
| `unknown` | The field may exist, but the current task cannot confirm it. |
| `not_applicable` | The field does not apply to the current report scope or sample. |

Rules:

- If no real trade sample is proven, `metadata.sample_status` must be
  `insufficient`.
- If SQLite/API/monitor evidence is not verified, numeric fields must not be
  written as `0`; use `missing` or `unknown`.
- Do not translate absent evidence into a verified empty dataset.
- Do not translate an unchecked anomaly source into a healthy runtime claim.
- `verdict.can_evaluate_replacement` must be `false` unless same-window
  V10.8.2 and V11.29 execution evidence is verified.

## Common Field Envelope

All report facts should use this envelope unless the field is pure metadata.

```json
{
  "state": "observed",
  "value": null,
  "unit": null,
  "source_refs": [],
  "confidence": "medium",
  "notes": ""
}
```

`state` is required. `source_refs` must point to data source IDs in
`metadata.data_sources` when `state` is `observed` or `derived`.

## JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://local.freqtrade-harness/schemas/v1129-execution-report.schema.json",
  "title": "V11.29 Execution Verification Report",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "metadata",
    "bot_runtime",
    "execution_samples",
    "trade_execution_quality",
    "strategy_behavior",
    "benchmark_comparison",
    "data_gaps",
    "verdict"
  ],
  "$defs": {
    "evidence_state": {
      "type": "string",
      "enum": ["observed", "derived", "missing", "unknown", "not_applicable"]
    },
    "confidence": {
      "type": "string",
      "enum": ["high", "medium", "low", "unknown"]
    },
    "field": {
      "type": "object",
      "additionalProperties": false,
      "required": ["state", "value", "source_refs", "confidence"],
      "properties": {
        "state": { "$ref": "#/$defs/evidence_state" },
        "value": {},
        "unit": { "type": ["string", "null"] },
        "source_refs": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "confidence": { "$ref": "#/$defs/confidence" },
        "notes": { "type": "string" }
      }
    },
    "data_source": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "path_or_endpoint", "read_status", "trust_level"],
      "properties": {
        "id": { "type": "string" },
        "kind": {
          "type": "string",
          "enum": ["sqlite", "json_report", "html_report", "dashboard_api", "script", "log", "config_path", "strategy_path", "other"]
        },
        "path_or_endpoint": { "type": "string" },
        "read_status": {
          "type": "string",
          "enum": ["read", "path_only", "not_read", "not_found", "blocked"]
        },
        "trust_level": { "$ref": "#/$defs/confidence" },
        "contains_secret_material": { "type": "boolean" },
        "notes": { "type": "string" }
      }
    }
  },
  "properties": {
    "metadata": {
      "type": "object",
      "additionalProperties": false,
      "required": ["strategy", "version", "report_time", "observation_window", "data_sources", "sample_status"],
      "properties": {
        "strategy": { "$ref": "#/$defs/field" },
        "version": { "$ref": "#/$defs/field" },
        "report_time": { "type": "string", "format": "date-time" },
        "observation_window": {
          "type": "object",
          "additionalProperties": false,
          "required": ["start", "end", "timezone", "state"],
          "properties": {
            "start": { "type": ["string", "null"], "format": "date-time" },
            "end": { "type": ["string", "null"], "format": "date-time" },
            "timezone": { "type": "string" },
            "state": { "$ref": "#/$defs/evidence_state" },
            "notes": { "type": "string" }
          }
        },
        "data_sources": {
          "type": "array",
          "items": { "$ref": "#/$defs/data_source" }
        },
        "sample_status": {
          "type": "string",
          "enum": ["sufficient", "insufficient", "unknown"]
        }
      }
    },
    "bot_runtime": {
      "type": "object",
      "additionalProperties": false,
      "required": ["running_state", "uptime", "stopped_alerts", "api_errors", "jq_parse_errors", "data_quality"],
      "properties": {
        "running_state": { "$ref": "#/$defs/field" },
        "uptime": { "$ref": "#/$defs/field" },
        "stopped_alerts": { "$ref": "#/$defs/field" },
        "api_errors": { "$ref": "#/$defs/field" },
        "jq_parse_errors": { "$ref": "#/$defs/field" },
        "data_quality": { "$ref": "#/$defs/field" }
      }
    },
    "execution_samples": {
      "type": "object",
      "additionalProperties": false,
      "required": ["total_trades", "open_trades", "closed_trades", "sample_1d", "sample_7d", "sample_14d", "sample_sufficiency"],
      "properties": {
        "total_trades": { "$ref": "#/$defs/field" },
        "open_trades": { "$ref": "#/$defs/field" },
        "closed_trades": { "$ref": "#/$defs/field" },
        "sample_1d": { "$ref": "#/$defs/field" },
        "sample_7d": { "$ref": "#/$defs/field" },
        "sample_14d": { "$ref": "#/$defs/field" },
        "sample_sufficiency": { "$ref": "#/$defs/field" }
      }
    },
    "trade_execution_quality": {
      "type": "object",
      "additionalProperties": false,
      "required": ["order_price", "expected_price", "filled_price", "slippage_bps", "fee", "funding_fee", "latency", "unfilled_signals", "blocked_signals"],
      "properties": {
        "order_price": { "$ref": "#/$defs/field" },
        "expected_price": { "$ref": "#/$defs/field" },
        "filled_price": { "$ref": "#/$defs/field" },
        "slippage_bps": { "$ref": "#/$defs/field" },
        "fee": { "$ref": "#/$defs/field" },
        "funding_fee": { "$ref": "#/$defs/field" },
        "latency": { "$ref": "#/$defs/field" },
        "unfilled_signals": { "$ref": "#/$defs/field" },
        "blocked_signals": { "$ref": "#/$defs/field" }
      }
    },
    "strategy_behavior": {
      "type": "object",
      "additionalProperties": false,
      "required": ["pair", "side", "entry_tag", "exit_reason", "open_time", "close_time", "pnl", "pnl_ratio"],
      "properties": {
        "pair": { "$ref": "#/$defs/field" },
        "side": { "$ref": "#/$defs/field" },
        "entry_tag": { "$ref": "#/$defs/field" },
        "exit_reason": { "$ref": "#/$defs/field" },
        "open_time": { "$ref": "#/$defs/field" },
        "close_time": { "$ref": "#/$defs/field" },
        "pnl": { "$ref": "#/$defs/field" },
        "pnl_ratio": { "$ref": "#/$defs/field" }
      }
    },
    "benchmark_comparison": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "v1082_data_availability",
        "same_window_comparison_availability",
        "comparison_1d_status",
        "comparison_7d_status",
        "comparison_14d_status",
        "cannot_compare_reason"
      ],
      "properties": {
        "v1082_data_availability": { "$ref": "#/$defs/field" },
        "same_window_comparison_availability": { "$ref": "#/$defs/field" },
        "comparison_1d_status": { "$ref": "#/$defs/field" },
        "comparison_7d_status": { "$ref": "#/$defs/field" },
        "comparison_14d_status": { "$ref": "#/$defs/field" },
        "cannot_compare_reason": { "$ref": "#/$defs/field" }
      }
    },
    "data_gaps": {
      "type": "object",
      "additionalProperties": false,
      "required": ["missing_fields", "unverified_fields", "required_new_collection", "blocking_gaps"],
      "properties": {
        "missing_fields": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        },
        "unverified_fields": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        },
        "required_new_collection": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        },
        "blocking_gaps": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        }
      }
    },
    "verdict": {
      "type": "object",
      "additionalProperties": false,
      "required": ["report_status", "can_generate_execution_report", "can_evaluate_replacement", "reason", "next_required_task"],
      "properties": {
        "report_status": {
          "type": "string",
          "enum": ["schema_only", "draft_from_observed_data", "blocked_by_missing_data", "final_from_observed_data"]
        },
        "can_generate_execution_report": { "$ref": "#/$defs/field" },
        "can_evaluate_replacement": { "$ref": "#/$defs/field" },
        "reason": { "$ref": "#/$defs/field" },
        "next_required_task": { "$ref": "#/$defs/field" }
      }
    }
  }
}
```

## Markdown Report Structure

A future Markdown report generated from this schema must use this order:

1. Summary
2. Data availability
3. Execution sample status
4. Runtime health
5. Execution quality
6. V10.8.2 comparison readiness
7. Missing data
8. Blocking gaps
9. What this report cannot conclude
10. Recommended next task

## Required Wording Controls

The report writer must preserve evidence boundaries:

- Use `sample_status = insufficient` when real trade samples are not proven.
- Use `missing` when a required source was checked and the field/path is absent.
- Use `unknown` when the source was not read, could not be queried, or cannot be
  confirmed by the current task.
- Use `observed` only for directly verified real execution data.
- Use `derived` only when the calculation inputs are `observed`.
- Keep replacement evaluation disabled unless same-window V11.29 and V10.8.2
  execution samples are verified.
- State that a report cannot conclude replacement readiness when the evidence is
  schema-only, path-only, or sample-insufficient.

## Minimal Sample-Insufficient Skeleton

```json
{
  "metadata": {
    "strategy": {
      "state": "unknown",
      "value": "RegimeAwareV1129ResidualDragMicroSizer",
      "unit": null,
      "source_refs": [],
      "confidence": "low",
      "notes": "Strategy path was identified by inventory, but runtime use was not verified."
    },
    "version": {
      "state": "unknown",
      "value": "V11.29",
      "unit": null,
      "source_refs": [],
      "confidence": "low",
      "notes": "Version label is path-derived until runtime source is verified."
    },
    "report_time": "2026-07-03T00:00:00+08:00",
    "observation_window": {
      "start": null,
      "end": null,
      "timezone": "Asia/Shanghai",
      "state": "unknown",
      "notes": "No verified execution window."
    },
    "data_sources": [],
    "sample_status": "insufficient"
  },
  "bot_runtime": {
    "running_state": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "uptime": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "stopped_alerts": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "api_errors": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "jq_parse_errors": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "data_quality": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" }
  },
  "execution_samples": {
    "total_trades": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "Do not use 0 unless a verified source reports zero." },
    "open_trades": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "" },
    "closed_trades": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "" },
    "sample_1d": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "" },
    "sample_7d": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "" },
    "sample_14d": { "state": "unknown", "value": null, "unit": "trades", "source_refs": [], "confidence": "unknown", "notes": "" },
    "sample_sufficiency": { "state": "derived", "value": "insufficient", "unit": null, "source_refs": [], "confidence": "medium", "notes": "Derived from absence of verified trade samples." }
  },
  "trade_execution_quality": {
    "order_price": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "expected_price": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "filled_price": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "slippage_bps": { "state": "unknown", "value": null, "unit": "bps", "source_refs": [], "confidence": "unknown", "notes": "" },
    "fee": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "funding_fee": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "latency": { "state": "unknown", "value": null, "unit": "seconds", "source_refs": [], "confidence": "unknown", "notes": "" },
    "unfilled_signals": { "state": "unknown", "value": null, "unit": "signals", "source_refs": [], "confidence": "unknown", "notes": "" },
    "blocked_signals": { "state": "unknown", "value": null, "unit": "signals", "source_refs": [], "confidence": "unknown", "notes": "" }
  },
  "strategy_behavior": {
    "pair": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "side": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "entry_tag": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "exit_reason": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "open_time": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "close_time": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "pnl": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "pnl_ratio": { "state": "unknown", "value": null, "unit": "ratio", "source_refs": [], "confidence": "unknown", "notes": "" }
  },
  "benchmark_comparison": {
    "v1082_data_availability": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "same_window_comparison_availability": { "state": "missing", "value": null, "unit": null, "source_refs": [], "confidence": "medium", "notes": "No same-window comparison source has been verified." },
    "comparison_1d_status": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "comparison_7d_status": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "comparison_14d_status": { "state": "unknown", "value": null, "unit": null, "source_refs": [], "confidence": "unknown", "notes": "" },
    "cannot_compare_reason": { "state": "derived", "value": "No verified same-window execution samples.", "unit": null, "source_refs": [], "confidence": "medium", "notes": "" }
  },
  "data_gaps": {
    "missing_fields": [],
    "unverified_fields": [],
    "required_new_collection": [],
    "blocking_gaps": []
  },
  "verdict": {
    "report_status": "schema_only",
    "can_generate_execution_report": { "state": "derived", "value": false, "unit": null, "source_refs": [], "confidence": "medium", "notes": "Requires verified execution samples first." },
    "can_evaluate_replacement": { "state": "derived", "value": false, "unit": null, "source_refs": [], "confidence": "medium", "notes": "Requires same-window comparison evidence first." },
    "reason": { "state": "derived", "value": "Schema exists, but execution evidence is not verified.", "unit": null, "source_refs": [], "confidence": "medium", "notes": "" },
    "next_required_task": { "state": "derived", "value": "Task 14: V11.29 Execution Data Collection Plan", "unit": null, "source_refs": [], "confidence": "medium", "notes": "" }
  }
}
```

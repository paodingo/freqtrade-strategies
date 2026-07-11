#!/usr/bin/env python3
"""Compare two fixed-backtest verification reruns and write a report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_experiment import compare_core_metrics


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_runs(repo_root: Path, campaign_id: str, experiment_id: int, first_run: str, second_run: str) -> dict:
    base = repo_root / "research" / "results" / campaign_id / str(experiment_id)
    first_dir = base / first_run
    second_dir = base / second_run
    first_report = load_json(first_dir / "runner-report.json")
    second_report = load_json(second_dir / "runner-report.json")
    first_metrics = load_json(first_dir / "metrics.json")
    second_metrics = load_json(second_dir / "metrics.json")
    metrics_compare = compare_core_metrics(first_metrics, second_metrics)
    same_input = first_report.get("input_fingerprint") == second_report.get("input_fingerprint")
    both_success = first_report.get("status") in {"accepted", "rejected"} and second_report.get("status") in {"accepted", "rejected"}
    consistent = bool(both_success and same_input and metrics_compare["consistent"])
    return {
        "campaign_id": campaign_id,
        "experiment_id": experiment_id,
        "first_run": first_run,
        "second_run": second_run,
        "first_status": first_report.get("status"),
        "second_status": second_report.get("status"),
        "same_input_fingerprint": same_input,
        "input_fingerprint": first_report.get("input_fingerprint"),
        "metrics_consistent": metrics_compare["consistent"],
        "consistent": consistent,
        "metrics_compare": metrics_compare,
        "first_metrics": first_metrics.get("normalized", {}),
        "second_metrics": second_metrics.get("normalized", {}),
        "first_result_path": str(first_dir / first_report.get("result_path", "")),
        "second_result_path": str(second_dir / second_report.get("result_path", "")),
    }


def write_markdown(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {result['campaign_id']} Reproducibility Report",
        "",
        f"- consistent: `{str(result['consistent']).lower()}`",
        f"- first_run: `{result['first_run']}` status `{result['first_status']}`",
        f"- second_run: `{result['second_run']}` status `{result['second_status']}`",
        f"- same_input_fingerprint: `{str(result['same_input_fingerprint']).lower()}`",
        f"- input_fingerprint: `{result['input_fingerprint']}`",
        f"- metrics_consistent: `{str(result['metrics_consistent']).lower()}`",
        f"- first_result_path: `{result['first_result_path']}`",
        f"- second_result_path: `{result['second_result_path']}`",
        "",
        "## Core Metrics",
        "",
        "| metric | RUN-A | RUN-B |",
        "|---|---:|---:|",
    ]
    for key in sorted(set(result["first_metrics"]) | set(result["second_metrics"])):
        if key == "pair_count":
            continue
        lines.append(f"| `{key}` | `{result['first_metrics'].get(key)}` | `{result['second_metrics'].get(key)}` |")
    if result["metrics_compare"]["differences"]:
        lines.extend(["", "## Differences", ""])
        for key, value in result["metrics_compare"]["differences"].items():
            lines.append(f"- `{key}`: `{value['first']}` vs `{value['second']}`")
    else:
        lines.extend(["", "## Differences", "", "None."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two verification reruns.")
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--first-run", default="RUN-A")
    parser.add_argument("--second-run", default="RUN-B")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo_root = Path.cwd()
    result = compare_runs(repo_root, args.campaign_id, args.experiment_id, args.first_run, args.second_run)
    report_path = repo_root / "research" / "reports" / f"{args.campaign_id}_reproducibility_report.md"
    write_markdown(report_path, result)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"consistent={str(result['consistent']).lower()} report={report_path}")
    return 0 if result["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

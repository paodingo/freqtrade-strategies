#!/usr/bin/env python3
"""Verify full-test failures against the recorded quality baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import os
from pathlib import Path
from typing import Any

from research_control import parse_scalar
from portable_baseline_fixtures import HYDRATED_PACK, PortableFixtureError, verify as verify_portable_pack


def load_baseline(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return load_baseline_without_yaml(text)


def load_baseline_without_yaml(text: str) -> dict:
    baseline: dict[str, Any] = {}
    section: str | None = None
    list_name: str | None = None
    current_item: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            baseline[section] = {}
            list_name = None
            current_item = None
            continue
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            baseline[key] = parse_scalar(value)
            continue
        if section is None:
            continue
        if indent == 2 and line.endswith(":"):
            list_name = line[:-1]
            baseline[section][list_name] = []
            current_item = None
            continue
        if indent == 2 and ":" in line:
            key, value = line.split(":", 1)
            baseline[section][key] = parse_scalar(value)
            continue
        if indent == 4 and line.startswith("- "):
            if list_name is None:
                raise ValueError("baseline list item outside list")
            current_item = {}
            baseline[section][list_name].append(current_item)
            rest = line[2:]
            if ":" in rest:
                key, value = rest.split(":", 1)
                current_item[key] = parse_scalar(value)
            continue
        if indent >= 6 and current_item is not None and ":" in line:
            key, value = line.split(":", 1)
            current_item[key] = parse_scalar(value)
    return baseline


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_python_failures(output: str) -> list[dict]:
    failures = []
    pattern = re.compile(r"ERROR: (?P<test>[^\n]+)\n[-]+\nTraceback.*?(?P<exception>[A-Za-z]+Error): (?P<message>.*?)(?=\n\n=|\n\n-+\nRan|\Z)", re.S)
    for match in pattern.finditer(output):
        test = match.group("test")
        expanded = re.search(r"\(([^()]+?\.[^()]+?\.[^()]+?)\)", test)
        if expanded:
            test = expanded.group(1)
        callback = re.search(r"\(callback='([^']+)'\)", match.group(0))
        if callback:
            test = f"{test}[{callback.group(1)}]"
        message = norm(match.group("message"))
        failures.append(
            {
                "test": norm(test),
                "exception": match.group("exception"),
                "fingerprint": fingerprint_for_message(message),
            }
        )
    failure_pattern = re.compile(r"FAIL: (?P<test>[^\n]+)\n[-]+\nTraceback.*?(?P<exception>AssertionError):? (?P<message>.*?)(?=\n\n=|\n\n-+\nRan|\Z)", re.S)
    for match in failure_pattern.finditer(output):
        test = match.group("test")
        expanded = re.search(r"\(([^()]+?\.[^()]+?\.[^()]+?)\)", test)
        if expanded:
            test = expanded.group(1)
        message = norm(match.group("message"))
        failures.append({"test": norm(test), "exception": match.group("exception"), "fingerprint": fingerprint_for_message(message)})
    return failures


def extract_node_failures(output: str) -> list[dict]:
    failures = []
    pattern = re.compile(r"✖ (?P<test>[^\n]+)\n\s+(?P<exception>[A-Za-z]+Error).*?(?=\n\ntest at|\n\n✖ failing tests:|\Z)", re.S)
    for match in pattern.finditer(output):
        body = match.group(0)
        test = re.sub(r"\s+\([0-9.]+ms\)$", "", norm(match.group("test")))
        failures.append(
            {
                "test": test,
                "exception": match.group("exception"),
                "fingerprint": fingerprint_for_message(norm(body)),
            }
        )
    return failures


def fingerprint_for_message(message: str) -> str:
    known = [
        ("custom_entry_price", "IStrategy has no attribute custom_entry_price"),
        ("custom_exit_price", "IStrategy has no attribute custom_exit_price"),
        ("adjust_trade_position", "IStrategy has no attribute adjust_trade_position"),
        ("monitor.sqlite", "monitor.sqlite another process is using this file"),
        ("0 !== 1", "0 !== 1"),
        ("2026-06-10T00:02:00.000Z", "actual [] expected 2026-06-10T00:02:00.000Z"),
    ]
    for needle, fp in known:
        if needle in message:
            return fp
    return message[:180]


def compare(section: str, observed: list[dict], expected: list[dict]) -> list[str]:
    errors = []
    expected_map = {item["test"]: item for item in expected}
    observed_map = {item["test"]: item for item in observed}
    for test, item in observed_map.items():
        if test not in expected_map:
            errors.append(f"{section}: new failure {test} ({item['exception']} / {item['fingerprint']})")
            continue
        expected_item = expected_map[test]
        if item["exception"] != expected_item["exception"] or item["fingerprint"] != expected_item["fingerprint"]:
            errors.append(
                f"{section}: changed failure {test}: "
                f"{item['exception']} / {item['fingerprint']} != "
                f"{expected_item['exception']} / {expected_item['fingerprint']}"
            )
    for test in expected_map:
        if test not in observed_map:
            errors.append(f"{section}: known failure disappeared {test}")
    return errors


def run_command(command: list[str], cwd: Path, environment: dict[str, str] | None = None) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        env=environment,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify current full-test failures against docs/quality/test-baseline.yaml.")
    parser.add_argument("--baseline", default="docs/quality/test-baseline.yaml")
    parser.add_argument("--python-output")
    parser.add_argument("--node-output")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--profile", choices=("authoritative_asset_audit", "clean_worktree_portable"), default="authoritative_asset_audit")
    parser.add_argument("--fixture-pack", default=str(HYDRATED_PACK))
    args = parser.parse_args()
    root = Path.cwd()
    baseline = load_baseline(root / args.baseline)
    profile_evidence: dict[str, Any] = {"profile_id": args.profile}
    environment = os.environ.copy()
    status_before = run_command(["git", "status", "--porcelain=v2", "--untracked-files=all"], root)[1]
    if args.profile == "clean_worktree_portable":
        try:
            pack = Path(args.fixture_pack).resolve()
            profile_evidence["fixture_pack"] = verify_portable_pack(pack)
        except PortableFixtureError as exc:
            print(json.dumps({"profile_id": args.profile, "errors": [exc.reason_code], "detail": str(exc)}, indent=2))
            return 1
        environment["PORTABLE_BASELINE_PACK_ROOT"] = str(pack)
        environment["PORTABLE_BASELINE_NETWORK"] = "forbidden"
        preload = (root / "scripts" / "block_portable_network.js").resolve()
        environment["NODE_OPTIONS"] = f"--require={preload}"

    if args.run:
        python_command = [sys.executable, "scripts/run_portable_test_suite.py"] if args.profile == "clean_worktree_portable" else [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
        py_code, py_output = run_command(python_command, root, environment)
        js_tests = [str(path.relative_to(root)) for path in sorted((root / "tests").glob("*.js"))]
        node_code, node_output = run_command(["node", "--test", *js_tests], root, environment)
    else:
        if not args.python_output or not args.node_output:
            raise SystemExit("--python-output and --node-output are required unless --run is used")
        py_output = Path(args.python_output).read_text(encoding="utf-8")
        node_output = Path(args.node_output).read_text(encoding="utf-8")
        py_code = node_code = 1

    observed_py = extract_python_failures(py_output)
    observed_node = extract_node_failures(node_output)
    errors = []
    errors.extend(compare("python", observed_py, baseline["python"]["known_failures"]))
    errors.extend(compare("node", observed_node, baseline["node"]["known_failures"]))
    status_after = run_command(["git", "status", "--porcelain=v2", "--untracked-files=all"], root)[1]
    if status_after != status_before:
        errors.append("portable baseline modified versioned worktree")
    report = {
        "python_returncode": py_code,
        "node_returncode": node_code,
        "python_failures": observed_py,
        "node_failures": observed_node,
        "errors": errors,
        "profile": profile_evidence,
        "versioned_worktree_unchanged": status_after == status_before,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Atomically recreate registered dry-run bots from an immutable release."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def docker(*args: str, check: bool = True) -> str:
    result = subprocess.run(["docker", *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return (result.stdout or result.stderr).strip()


def exists(name: str) -> bool:
    return bool(docker("ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}", check=False))


def validate(release: Path, legacy: Path) -> tuple[dict, dict]:
    deployment = json.loads((release / "runtime-deployment-manifest.json").read_text(encoding="utf-8"))
    runtime = json.loads((release / "deploy" / "runtime-bots.json").read_text(encoding="utf-8"))
    if deployment.get("dry_run_only") is not True:
        raise RuntimeError("refusing to reconcile bots from a non-dry-run release")
    if runtime.get("schema_version") != "dry-run-bot-runtime-v1" or "@sha256:" not in runtime.get("image", ""):
        raise RuntimeError("bot runtime must pin a digest")
    for bot in runtime.get("bots", []):
        config_name = Path(bot["config"]).name
        config_path = legacy / "user_data" / config_name
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("dry_run") is not True:
            raise RuntimeError(f"refusing non-dry-run config: {config_path}")
    return deployment, runtime


def wait_running(name: str, seconds: int = 35) -> None:
    initial_restarts = int(docker("inspect", "--format", "{{.RestartCount}}", name, check=False) or 0)
    for _ in range(seconds):
        state = docker("inspect", "--format", "{{.State.Status}}", name, check=False)
        if state == "running":
            restarts = int(docker("inspect", "--format", "{{.RestartCount}}", name, check=False) or 0)
            started_at = docker("inspect", "--format", "{{.State.StartedAt}}", name, check=False)
            time.sleep(1)
            stable = (
                docker("inspect", "--format", "{{.State.Status}}", name, check=False) == "running"
                and int(docker("inspect", "--format", "{{.RestartCount}}", name, check=False) or 0) == restarts
                and docker("inspect", "--format", "{{.State.StartedAt}}", name, check=False) == started_at
            )
            if stable and restarts == initial_restarts and started_at and _ >= 14:
                return
        if state in {"exited", "dead"}:
            break
        time.sleep(1)
    logs = docker("logs", "--tail", "80", name, check=False)
    raise RuntimeError(f"container {name} did not remain running: {logs}")


def run_bot(bot: dict, image: str, release: Path, legacy: Path, git_sha: str) -> None:
    command = [
        "run", "-d", "--name", bot["name"], "--restart", "unless-stopped",
        "--label", "freqtrade.release.managed=true",
        "--label", f"freqtrade.release.git_sha={git_sha}",
        "-v", f"{legacy}:/freqtrade/project",
        "-v", f"{release}:/freqtrade/release:ro",
    ]
    for port in bot.get("ports", []):
        command.extend(["-p", port])
    command.extend([
        image, "trade", "--config", bot["config"], "--strategy", bot["strategy"],
        "--strategy-path", bot["strategy_path"],
    ])
    if bot.get("datadir"):
        command.extend(["--datadir", bot["datadir"]])
    if bot.get("initial_state"):
        command.extend(["--initial-state", bot["initial_state"]])
    docker(*command)
    wait_running(bot["name"])


def reconcile(release: Path, legacy: Path) -> None:
    deployment, runtime = validate(release, legacy)
    image = runtime["image"]
    git_sha = deployment["git_sha"]
    docker("pull", image)
    backups: list[tuple[str, str]] = []
    created: list[str] = []
    stamp = str(int(time.time()))
    try:
        for bot in runtime["bots"]:
            name = bot["name"]
            if exists(name):
                backup = f"{name}-previous-{stamp}"
                docker("stop", name)
                docker("rename", name, backup)
                backups.append((name, backup))
            run_bot(bot, image, release, legacy, git_sha)
            created.append(name)
    except Exception:
        for name in created:
            docker("rm", "-f", name, check=False)
        for name, backup in reversed(backups):
            if exists(name):
                docker("rm", "-f", name, check=False)
            docker("rename", backup, name, check=False)
            docker("start", name, check=False)
        raise
    for _, backup in backups:
        docker("rm", backup, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    args = parser.parse_args()
    reconcile(args.release.resolve(), args.legacy.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

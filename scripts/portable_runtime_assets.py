#!/usr/bin/env python3
"""Manifest, hydration, and verification primitives for the portable Freqtrade Runtime."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable


RUNTIME_ID = "portable-freqtrade-2025.8-python-3.12.13-ccxt-4.5.64-v1"
APPROVED_SOURCE_ROOT = Path("D:/code/freqtrade-strategies-clean/.venv-freqtrade")
TARGET_ROOT = Path(".venv-freqtrade")
MANIFEST_PATH = Path("research/runtime/portable-runtime-assets-freqtrade-2025.8.json")
PYTHON_VERSION = "3.12.13"
FREQTRADE_VERSION = "2025.8"
CCXT_VERSION = "4.5.64"
LEVERAGE_TIER_RELATIVE = Path("Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json")
LEVERAGE_TIER_SHA256 = "3cbdcc23ac57dd40e8664036293947fbe283865ef4a0f87e9265bb441858d981"
LEVERAGE_TIER_BYTES = 2176158


class PortableRuntimeError(RuntimeError):
    pass


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_fingerprint(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({key: value for key, value in payload.items() if key != "manifest_fingerprint"}).encode("utf-8"))


def is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def assert_no_reparse_tree(root: Path) -> None:
    if is_reparse_point(root):
        raise PortableRuntimeError(f"runtime_reparse_point_forbidden:{root}")
    for path in root.rglob("*"):
        if is_reparse_point(path):
            raise PortableRuntimeError(f"runtime_reparse_point_forbidden:{path}")


def is_selected_runtime_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if path.suffix.lower() in {".pyc", ".pyo"}:
        return False
    return "__pycache__" not in relative.parts


def selected_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and is_selected_runtime_file(path, root)),
        key=lambda path: path.relative_to(root).as_posix().lower(),
    )


def component_for(relative: str) -> tuple[str, str]:
    lower = relative.lower()
    if lower == "pyvenv.cfg" or lower.startswith("scripts/"):
        return "python_runtime_bootstrap", PYTHON_VERSION
    if lower.startswith("lib/site-packages/freqtrade/") or "/freqtrade-" in lower:
        return "freqtrade", FREQTRADE_VERSION
    if lower.startswith("lib/site-packages/ccxt/") or "/ccxt-" in lower:
        return "ccxt", CCXT_VERSION
    return "runtime_dependency_or_package_data", FREQTRADE_VERSION


def content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if path.name.lower() in {"python.exe", "pythonw.exe"}:
        return "python_executable"
    if suffix == ".py":
        return "python_source"
    if suffix in {".dll", ".pyd", ".exe"}:
        return "native_runtime_binary"
    if any(part.lower().endswith(".dist-info") for part in path.parts):
        return "package_metadata"
    return "non_python_package_data"


def runtime_identity(python: Path) -> dict[str, Any]:
    code = (
        "import importlib.metadata as m,json,sys;"
        "from freqtrade.optimize.backtesting import Backtesting;"
        "print(json.dumps({'python':sys.version.split()[0],'executable':sys.executable,"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix,'freqtrade':m.version('freqtrade'),"
        "'ccxt':m.version('ccxt'),'backtesting_import':Backtesting.__module__}))"
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    completed = subprocess.run([str(python), "-B", "-I", "-c", code], text=True, capture_output=True, check=False, timeout=120, env=env)
    if completed.returncode != 0:
        raise PortableRuntimeError(f"runtime_identity_failed:{completed.stderr[-2000:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    expected = {"python": PYTHON_VERSION, "freqtrade": FREQTRADE_VERSION, "ccxt": CCXT_VERSION}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise PortableRuntimeError(f"runtime_version_mismatch:{payload}")
    return payload


def build_manifest(source_root: Path = APPROVED_SOURCE_ROOT) -> dict[str, Any]:
    source_root = source_root.resolve()
    if source_root != APPROVED_SOURCE_ROOT.resolve():
        raise PortableRuntimeError(f"unapproved_runtime_source:{source_root}")
    if not source_root.is_dir():
        raise PortableRuntimeError(f"approved_runtime_source_missing:{source_root}")
    assert_no_reparse_tree(source_root)
    identity = runtime_identity(source_root / "Scripts/python.exe")
    files = selected_files(source_root)
    with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as pool:
        hashes = list(pool.map(sha256_file, files))
    entries: list[dict[str, Any]] = []
    directories: set[str] = set()
    for path, digest in zip(files, hashes):
        relative = path.relative_to(source_root).as_posix()
        component, version = component_for(relative)
        parent = Path(relative).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
        entries.append({
            "repo_relative_target": (TARGET_ROOT / relative).as_posix(),
            "source_relative_path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "source_runtime_id": RUNTIME_ID,
            "source_runtime_version": version,
            "component": component,
            "content_type": content_type(path),
        })
    leverage = next((entry for entry in entries if entry["source_relative_path"] == LEVERAGE_TIER_RELATIVE.as_posix()), None)
    if leverage is None or leverage["bytes"] != LEVERAGE_TIER_BYTES or leverage["sha256"] != LEVERAGE_TIER_SHA256:
        raise PortableRuntimeError("approved_leverage_tier_drift")
    base_prefix = Path(identity["base_prefix"])
    host_prerequisites = []
    for name in ("python.exe", "python3.dll", "python312.dll"):
        path = base_prefix / name
        if path.is_file():
            host_prerequisites.append({"absolute_path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path), "source_runtime_id": RUNTIME_ID, "source_runtime_version": PYTHON_VERSION})
    manifest: dict[str, Any] = {
        "schema_version": "portable-runtime-asset-manifest-v1",
        "runtime_id": RUNTIME_ID,
        "approved_source_root": source_root.as_posix(),
        "repo_relative_target_root": TARGET_ROOT.as_posix(),
        "versions": {"python": PYTHON_VERSION, "freqtrade": FREQTRADE_VERSION, "ccxt": CCXT_VERSION},
        "source_identity": identity,
        "selection_policy": {"include_all_files": True, "excluded_suffixes": [".pyc", ".pyo"], "excluded_directories": ["__pycache__"], "reject_reparse_points": True, "reject_target_extra_files": True},
        "host_python_prerequisites": host_prerequisites,
        "directories": sorted(directories),
        "files": entries,
        "file_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "leverage_tiers": {"repo_relative_target": (TARGET_ROOT / LEVERAGE_TIER_RELATIVE).as_posix(), "source": (source_root / LEVERAGE_TIER_RELATIVE).as_posix(), "bytes": LEVERAGE_TIER_BYTES, "sha256": LEVERAGE_TIER_SHA256},
    }
    manifest["manifest_fingerprint"] = manifest_fingerprint(manifest)
    return manifest


def load_manifest(repo: Path, path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads((repo / path).read_text(encoding="utf-8"))
    if manifest.get("manifest_fingerprint") != manifest_fingerprint(manifest):
        raise PortableRuntimeError("runtime_manifest_fingerprint_mismatch")
    if manifest.get("runtime_id") != RUNTIME_ID or manifest.get("versions") != {"python": PYTHON_VERSION, "freqtrade": FREQTRADE_VERSION, "ccxt": CCXT_VERSION}:
        raise PortableRuntimeError("runtime_manifest_authority_mismatch")
    return manifest


def _entry_relative(entry: dict[str, Any]) -> Path:
    target = Path(entry["repo_relative_target"])
    try:
        return target.relative_to(TARGET_ROOT)
    except ValueError as exc:
        raise PortableRuntimeError(f"runtime_target_outside_root:{target}") from exc


def verify_source(manifest: dict[str, Any], source_root: Path) -> None:
    source_root = source_root.resolve()
    if source_root != Path(manifest["approved_source_root"]).resolve() or source_root != APPROVED_SOURCE_ROOT.resolve():
        raise PortableRuntimeError(f"unapproved_runtime_source:{source_root}")
    assert_no_reparse_tree(source_root)
    actual = {path.relative_to(source_root).as_posix() for path in selected_files(source_root)}
    expected = {entry["source_relative_path"] for entry in manifest["files"]}
    if actual != expected:
        raise PortableRuntimeError(f"runtime_source_file_set_drift:missing={len(expected - actual)}:extra={len(actual - expected)}")
    for prerequisite in manifest.get("host_python_prerequisites", []):
        path = Path(prerequisite["absolute_path"])
        if not path.is_file() or path.stat().st_size != prerequisite["bytes"] or sha256_file(path) != prerequisite["sha256"]:
            raise PortableRuntimeError(f"host_python_prerequisite_drift:{path}")
    if runtime_identity(source_root / "Scripts/python.exe")["base_prefix"] != manifest["source_identity"]["base_prefix"]:
        raise PortableRuntimeError("runtime_base_python_drift")


def _hash_entries(root: Path, entries: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Path, str | None]]:
    paths = [root / _entry_relative(entry) for entry in entries]

    def calculate(path: Path) -> str | None:
        return sha256_file(path) if path.is_file() else None

    with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as pool:
        hashes = list(pool.map(calculate, paths))
    return list(zip(entries, paths, hashes))


def verify_runtime_files(repo: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    manifest = manifest or load_manifest(repo)
    target_root = repo / TARGET_ROOT
    if not target_root.is_dir():
        raise PortableRuntimeError(f"portable_runtime_missing:{TARGET_ROOT.as_posix()}")
    assert_no_reparse_tree(target_root)
    expected_files = {_entry_relative(entry).as_posix() for entry in manifest["files"]}
    actual_files = {path.relative_to(target_root).as_posix() for path in target_root.rglob("*") if path.is_file()}
    if actual_files != expected_files:
        raise PortableRuntimeError(f"portable_runtime_file_set_mismatch:missing={len(expected_files - actual_files)}:extra={len(actual_files - expected_files)}")
    expected_dirs = set(manifest["directories"])
    actual_dirs = {path.relative_to(target_root).as_posix() for path in target_root.rglob("*") if path.is_dir()}
    if actual_dirs != expected_dirs:
        raise PortableRuntimeError(f"portable_runtime_directory_set_mismatch:missing={len(expected_dirs - actual_dirs)}:extra={len(actual_dirs - expected_dirs)}")
    failures = []
    for entry, path, digest in _hash_entries(target_root, manifest["files"]):
        if digest != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            failures.append(entry["repo_relative_target"])
    if failures:
        raise PortableRuntimeError(f"portable_runtime_hash_mismatch:{failures[:5]}")
    leverage = target_root / LEVERAGE_TIER_RELATIVE
    if leverage.stat().st_size != LEVERAGE_TIER_BYTES or sha256_file(leverage) != LEVERAGE_TIER_SHA256:
        raise PortableRuntimeError("portable_runtime_leverage_tier_mismatch")
    return {"status": "passed", "manifest_fingerprint": manifest["manifest_fingerprint"], "file_count": manifest["file_count"], "total_bytes": manifest["total_bytes"], "target_root": target_root.as_posix(), "leverage_tier_sha256": LEVERAGE_TIER_SHA256}


def hydrate_runtime(repo: Path, source_root: Path = APPROVED_SOURCE_ROOT) -> dict[str, Any]:
    repo = repo.resolve()
    manifest = load_manifest(repo)
    verify_source(manifest, source_root)
    target_root = repo / TARGET_ROOT
    if target_root.exists():
        verification = verify_runtime_files(repo, manifest)
        return {**verification, "hydrated": False, "reason": "already_exact"}
    stage_parent = Path(tempfile.mkdtemp(prefix="portable-runtime-hydration-", dir=repo.parent))
    stage_root = stage_parent / TARGET_ROOT.name
    stage_root.mkdir()
    try:
        for entry in manifest["files"]:
            source = source_root / entry["source_relative_path"]
            if is_reparse_point(source) or not source.is_file() or source.stat().st_size != entry["bytes"] or sha256_file(source) != entry["sha256"]:
                raise PortableRuntimeError(f"runtime_source_asset_mismatch:{source}")
            target = stage_root / _entry_relative(entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for entry, path, digest in _hash_entries(stage_root, manifest["files"]):
            if digest != entry["sha256"] or path.stat().st_size != entry["bytes"]:
                raise PortableRuntimeError(f"hydrated_asset_mismatch:{entry['repo_relative_target']}")
        os.replace(stage_root, target_root)
    finally:
        shutil.rmtree(stage_parent, ignore_errors=True)
    verification = verify_runtime_files(repo, manifest)
    return {**verification, "hydrated": True, "source_root": source_root.resolve().as_posix()}


def subprocess_environment() -> dict[str, str]:
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PORTABLE_BASELINE_NETWORK": "forbidden"}


def run_command(command: Iterable[str], *, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout, env=subprocess_environment())
